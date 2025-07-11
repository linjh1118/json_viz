#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
眼科图片问答脚本
调用豆包模型为每一个图片-问题对生成两个高温答案，并生成HTML可视化
"""

import os
import sys
import json
import pandas as pd
import base64
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any

# 添加API路径
sys.path.append('/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/code/0702_verifier/0001_utils/api')
# 添加json_viz包的路径
sys.path.append('/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/external/json_viz/src')

from call_doubao_api import DoubaoAPIClient


# 配置参数
INPUT_DIR = "/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/code/0702_verifier/exp_tagger/shibiao_data/images"
OUTPUT_DIR = "/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/code/0702_verifier/exp_tagger/shibiao_data/results"
PROMPT_FILE = os.path.join(INPUT_DIR, "prompt.txt")
HIGH_TEMPERATURE = 0.9  # 高温设置
MAX_WORKERS = 4  # 最大线程数


def load_questions(prompt_file: str) -> List[str]:
    """加载问题列表"""
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            questions = [line.strip() for line in f.readlines() if line.strip()]
        print(f"✅ 成功加载 {len(questions)} 个问题")
        return questions
    except Exception as e:
        print(f"❌ 加载问题失败: {e}")
        return []


def get_image_files(input_dir: str) -> List[str]:
    """获取图片文件列表（按数字顺序排序）"""
    image_files = []
    for i in range(1, 11):  # 1.png 到 10.png
        image_path = os.path.join(input_dir, f"{i}.png")
        if os.path.exists(image_path):
            image_files.append(image_path)
        else:
            print(f"⚠️ 警告: 图片文件不存在: {image_path}")
    
    print(f"✅ 找到 {len(image_files)} 张图片")
    return image_files


def image_to_base64(image_path: str) -> str:
    """
    将本地图片转换为base64格式
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        base64编码的图片字符串
    """
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:image/png;base64,{encoded_string}"
    except Exception as e:
        print(f"❌ 图片转换base64失败: {e}")
        return ""


def call_doubao_with_high_temp(client: DoubaoAPIClient, image_path: str, question: str) -> dict:
    """
    使用高温参数调用豆包模型
    
    Args:
        client: 豆包API客户端
        image_path: 图片路径
        question: 问题文本
        
    Returns:
        模型回答内容
    """
    try:
        # 将图片转换为base64格式
        image_base64 = image_to_base64(image_path)
        if not image_base64:
            return "图片转换失败"
        
        # 使用base64格式的图片创建消息
        message = client.create_multimodal_message(question, image_base64)
        result_dict = client.chat_completion(
            messages=[message],
            temperature=HIGH_TEMPERATURE,  # 设置高温
            max_tokens=2000,  # 限制回答长度
            top_p=0.9,  # 添加top_p参数
            enable_thinking=True  # 启用thinking功能
        )
        return result_dict
        
        # 提取回答内容
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0].get("message", {}).get("content", "")
            return content
        else:
            return "未获取到有效回答"
        
            
    except Exception as e:
        print(f"❌ API调用失败: {e}")
        return {"error": str(e)}


def generate_single_answer(client: DoubaoAPIClient, image_path: str, question: str, answer_id: int) -> tuple:
    """
    生成单个答案
    
    Args:
        client: 豆包API客户端
        image_path: 图片路径
        question: 问题文本
        answer_id: 答案ID（1或2）
        
    Returns:
        (answer_id, answer_text, answer_length)
    """
    print(f"  🔄 生成第 {answer_id} 个答案...")
    result_dict = call_doubao_with_high_temp(client, image_path, question)
    
    if "error" in result_dict:
        answer = f"调用失败: {result_dict['error']}"
    else:
        # 提取thinking和content
        reasoning_content = result_dict["choices"][0].get("message", {}).get("reasoning_content", "")
        content = result_dict["choices"][0].get("message", {}).get("content", "")
        answer = f"<think>{reasoning_content}</think><answer>{content}</answer>"
    
    print(f"  ✅ 答案 {answer_id} 已生成 ({len(answer)} 字符)")
    return answer_id, answer, len(answer)


def process_single_qa_pair(client: DoubaoAPIClient, image_path: str, question: str, qa_index: int, total_pairs: int) -> Dict[str, Any]:
    """
    处理单个图片-问题对，生成两个高温答案
    
    Args:
        client: 豆包API客户端
        image_path: 图片路径
        question: 问题文本
        qa_index: QA对的索引
        total_pairs: 总的QA对数量
        
    Returns:
        处理结果字典
    """
    print(f"\n📊 处理第 {qa_index+1}/{total_pairs} 个: {os.path.basename(image_path)}")
    print(f"❓ 问题: {question[:50]}...")
    
    # 并行生成两个答案
    answers = [None, None]
    answer_lengths = [0, 0]
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        # 提交两个答案生成任务
        future_to_answer = {
            executor.submit(generate_single_answer, client, image_path, question, 1): 1,
            executor.submit(generate_single_answer, client, image_path, question, 2): 2
        }
        
        # 收集结果
        for future in as_completed(future_to_answer):
            answer_id, answer_text, answer_length = future.result()
            answers[answer_id - 1] = answer_text
            answer_lengths[answer_id - 1] = answer_length
    
    # 整理结果
    result = {
        "序号": qa_index + 1,
        "图片文件": os.path.basename(image_path),
        "图片路径": image_path,
        "image": image_path,  # 用于json_viz显示图片
        "问题": question,
        "答案1": answers[0],
        "答案2": answers[1],
        "答案1长度": answer_lengths[0],
        "答案2长度": answer_lengths[1],
        "温度参数": HIGH_TEMPERATURE
    }
    
    print(f"✅ 第 {qa_index+1} 个图片-问题对处理完成")
    return result


def process_image_questions(client: DoubaoAPIClient, image_files: List[str], questions: List[str]) -> List[Dict[str, Any]]:
    """
    并行处理所有图片-问题对，为每个生成两个高温答案
    
    Args:
        client: 豆包API客户端
        image_files: 图片文件列表
        questions: 问题列表
        
    Returns:
        处理结果列表
    """
    total_pairs = len(image_files)
    print(f"🚀 开始并行处理 {total_pairs} 个图片-问题对，每个生成2个高温答案...")
    print(f"🔧 使用 {MAX_WORKERS} 个线程并行处理...")
    
    results = [None] * total_pairs  # 预分配结果列表以保持顺序
    
    # 使用ThreadPoolExecutor并行处理所有QA对
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务
        future_to_index = {
            executor.submit(process_single_qa_pair, client, image_path, question, i, total_pairs): i
            for i, (image_path, question) in enumerate(zip(image_files, questions))
        }
        
        # 收集结果
        completed_count = 0
        for future in as_completed(future_to_index):
            qa_index = future_to_index[future]
            try:
                result = future.result()
                results[qa_index] = result
                completed_count += 1
                print(f"🎯 已完成 {completed_count}/{total_pairs} 个QA对")
            except Exception as e:
                print(f"❌ 处理第 {qa_index+1} 个QA对时出错: {e}")
                # 创建错误结果
                results[qa_index] = {
                    "序号": qa_index + 1,
                    "图片文件": os.path.basename(image_files[qa_index]),
                    "图片路径": image_files[qa_index],
                    "image": image_files[qa_index],
                    "问题": questions[qa_index],
                    "答案1": f"处理失败: {str(e)}",
                    "答案2": f"处理失败: {str(e)}",
                    "答案1长度": len(f"处理失败: {str(e)}"),
                    "答案2长度": len(f"处理失败: {str(e)}"),
                    "温度参数": HIGH_TEMPERATURE
                }
    
    print(f"\n🎉 所有 {total_pairs} 个图片-问题对处理完成！")
    return results


def generate_html_visualization(results: List[Dict[str, Any]], output_dir: str) -> str:
    """生成HTML可视化"""
    try:
        from json_viz.core import JsonVisualizer
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 转换为DataFrame
        df = pd.DataFrame(results)
        
        # 生成可视化文件
        output_file = os.path.join(output_dir, "shibiao_qa_results.html")
        
        print(f"📊 正在生成HTML可视化: {output_file}")
        
        # 指定文本列
        textual_cols = ['问题', '答案1', '答案2']
        
        # 处理DataFrame
        processed_df = JsonVisualizer.process_dataframe(
            df, 
            textual_cols=textual_cols
        )
        
        # 生成HTML
        html_content = JsonVisualizer.generate_html(
            processed_df,
            title=f"眼科图片问答结果 - 10个QA对，高温度({HIGH_TEMPERATURE})生成",
            original_data=df
        )
        
        # 保存文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ HTML可视化已生成: {output_file}")
        
        # 保存JSON结果
        json_file = os.path.join(output_dir, "shibiao_qa_results.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"💾 JSON结果已保存: {json_file}")
        
        return output_file
        
    except Exception as e:
        print(f"❌ 生成HTML可视化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_summary_report(results: List[Dict[str, Any]], output_dir: str):
    """生成数据摘要报告"""
    try:
        # 计算统计信息
        total_qa_pairs = len(results)
        total_answers = total_qa_pairs * 2
        
        answer_lengths = []
        for result in results:
            answer_lengths.append(result['答案1长度'])
            answer_lengths.append(result['答案2长度'])
        
        avg_length = sum(answer_lengths) / len(answer_lengths) if answer_lengths else 0
        min_length = min(answer_lengths) if answer_lengths else 0
        max_length = max(answer_lengths) if answer_lengths else 0
        
        # 生成摘要
        summary = {
            "实验基本信息": {
                "数据集": "眼科图片问答数据集",
                "图片数量": total_qa_pairs,
                "问题数量": total_qa_pairs,
                "生成答案总数": total_answers,
                "温度参数": HIGH_TEMPERATURE,
                "模型": "豆包多模态模型"
            },
            "答案长度统计": {
                "平均长度": round(avg_length, 2),
                "最短答案": min_length,
                "最长答案": max_length
            },
            "处理状态": {
                "成功处理的QA对": total_qa_pairs,
                "失败的QA对": 0  # 如果有失败的话需要计算
            }
        }
        
        # 保存摘要报告
        summary_file = os.path.join(output_dir, "summary_report.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"📋 摘要报告已生成: {summary_file}")
        
        # 打印摘要到控制台
        print("\n" + "="*50)
        print("📊 实验摘要报告:")
        print(f"  • 处理了 {total_qa_pairs} 个图片-问题对")
        print(f"  • 生成了 {total_answers} 个高温答案")
        print(f"  • 平均答案长度: {avg_length:.0f} 字符")
        print(f"  • 温度参数: {HIGH_TEMPERATURE}")
        print("="*50)
        
    except Exception as e:
        print(f"❌ 生成摘要报告失败: {e}")


def main():
    """主函数"""
    print("🏥 眼科图片问答脚本启动")
    print("="*60)
    
    # 检查目录和文件
    if not os.path.exists(INPUT_DIR):
        print(f"❌ 错误: 输入目录不存在: {INPUT_DIR}")
        return 1
    
    if not os.path.exists(PROMPT_FILE):
        print(f"❌ 错误: 问题文件不存在: {PROMPT_FILE}")
        return 1
    
    # 加载数据
    print("📁 加载数据...")
    questions = load_questions(PROMPT_FILE)
    image_files = get_image_files(INPUT_DIR)
    
    if len(questions) != len(image_files):
        print(f"❌ 错误: 问题数量({len(questions)})与图片数量({len(image_files)})不匹配")
        return 1
    
    if not questions or not image_files:
        print("❌ 错误: 没有找到有效的问题或图片")
        return 1
    
    # 创建豆包客户端
    print("🔧 初始化豆包API客户端...")
    try:
        client = DoubaoAPIClient()
        print("✅ 豆包API客户端初始化成功")
    except Exception as e:
        print(f"❌ 初始化豆包API客户端失败: {e}")
        return 1
    
    # 处理图片-问题对
    print(f"🚀 开始处理，温度参数: {HIGH_TEMPERATURE}")
    results = process_image_questions(client, image_files, questions)
    
    if not results:
        print("❌ 没有生成任何结果")
        return 1
    
    # 生成可视化和报告
    print("📊 生成结果可视化...")
    html_file = generate_html_visualization(results, OUTPUT_DIR)
    
    print("📋 生成摘要报告...")
    generate_summary_report(results, OUTPUT_DIR)
    
    if html_file:
        print(f"\n🎉 所有任务完成!")
        print(f"📄 HTML可视化: {html_file}")
        print(f"📁 输出目录: {OUTPUT_DIR}")
    else:
        print("⚠️ 部分任务完成，但HTML生成失败")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
