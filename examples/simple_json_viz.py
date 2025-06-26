#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的JSON可视化脚本
直接使用json_viz对指定的JSON文件进行可视化
"""

import sys
import os
import argparse
from pathlib import Path

# 添加json_viz包的路径
sys.path.append('/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/external/json_viz/src')

try:
    from json_viz.core import JsonVisualizer
    print("✅ json_viz 模块导入成功")
except ImportError as e:
    print(f"❌ 错误: 无法导入 json_viz: {e}")

def visualize_json_file(input_file, output_file=None, title=None):
    """可视化JSON文件"""
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"❌ 错误: 输入文件不存在: {input_file}")
        return False
    
    # 设置默认输出文件
    if output_file is None:
        input_path = Path(input_file)
        output_file = input_path.parent / f"{input_path.stem}_visualization.html"
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # 设置默认标题
    if title is None:
        title = f"JSON数据可视化: {os.path.basename(input_file)}"
    
    # 定义常见的文本列
    textual_cols = [
        'Q', 'A', 'question', 'answer', 'instruction', 'output', 'input',
        'conversations', 'messages', 'text', 'content', 'response',
        'human', 'assistant', 'user', 'gpt', 'reasoning', 'explanation'
    ]
    try:
        print(f"🔄 开始生成可视化...")
        print(f"   输入文件: {input_file}")
        print(f"   输出文件: {output_file}")
        print(f"   标题: {title}")
        
        # 使用JsonVisualizer生成可视化
        JsonVisualizer.visualize(
            input_file=input_file,
            output_file=output_file,
            title=title,
            textual_cols=textual_cols,
            sample_size=50
        )
        
        print(f"✅ 可视化生成成功!")
        print(f"   请打开文件查看: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ 生成可视化时出错: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='使用json_viz可视化JSON文件')
    parser.add_argument('--input_file', help='要可视化的JSON文件路径')
    parser.add_argument('-o', '--output', help='输出HTML文件路径（可选）')
    parser.add_argument('-t', '--title', help='可视化页面标题（可选）')
    
    args = parser.parse_args()
    
    print("JSON文件可视化工具")
    print("=" * 50)

    
    # 执行可视化
    success = visualize_json_file(
        input_file=args.input_file,
        output_file=args.output,
        title=args.title
    )
    
    if success:
        print("\n🎉 可视化完成!")
    else:
        print("\n❌ 可视化失败!")

if __name__ == "__main__":
    # 如果没有命令行参数，使用默认的文件路径
    if len(sys.argv) == 1:
        print("使用默认文件路径进行可视化...")
        default_input = "/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/code/0615_coldstart/assets/complex_diseases_nejm/complex_diseases_with_reasoning_en_zh_train_db.json"
        
        if check_json_viz():
            visualize_json_file(
                input_file=default_input,
                title="Complex Diseases NEJM 数据集可视化"
            )
    else:
        main() 