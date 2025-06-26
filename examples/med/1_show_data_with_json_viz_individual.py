#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据可视化脚本 - 单独文件版本
使用 json_viz 生成单独采样数据的可视化HTML
"""

import json
import os
import glob
import sys
import tempfile
from pathlib import Path

# 添加json_viz包的路径
sys.path.append('/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/external/json_viz/src')

# 配置
INPUT_DIR = "/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/code/0609_difficulty/input_individual"
OUTPUT_DIR = "/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/code/0609_difficulty/visualization_individual"

# INPUT_DIR = "/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/code/0609_difficulty/input_individual_100"
# OUTPUT_DIR = "/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/code/0609_difficulty/visualization_individual_100"

IMAGE_BASE_PATH = "/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/DATA"

def check_json_viz():
    """检查json_viz是否可用"""
    try:
        from json_viz.core import JsonVisualizer
        print("json_viz 模块导入成功")
        return True
    except ImportError as e:
        print(f"错误: 无法导入 json_viz: {e}")
        return False

def process_sharegpt_messages(messages):
    """处理sharegpt格式和OpenAI格式的messages，提取Q和A"""
    if not isinstance(messages, list):
        return None, None
    
    questions = []
    answers = []
    
    for msg in messages:
        if isinstance(msg, dict):
            # 支持sharegpt格式 (from/value)
            role = msg.get('from', '').lower()
            content = msg.get('value', '')
            
            # 支持OpenAI格式 (role/content)
            if not role and not content:
                role = msg.get('role', '').lower()
                content = msg.get('content', '')
            
            if role in ['human', 'user']:
                questions.append(content)
            elif role in ['assistant', 'gpt']:
                answers.append(content)
    
    # 合并多轮对话
    q_text = '\n\n--- 下一轮 ---\n\n'.join(questions) if questions else ''
    a_text = '\n\n--- 下一轮 ---\n\n'.join(answers) if answers else ''
    
    return q_text, a_text

def fix_image_paths(images):
    """修复图片路径，将DATA替换为实际路径"""
    IMAGE_BASE_PATH = "/mnt/bn/med-mllm-lfv2"
    
    if not images:
        return images
    
    if isinstance(images, str):
        if images.startswith('DATA/'):
            return images.replace('DATA/', IMAGE_BASE_PATH + '/')
        return images
    
    if isinstance(images, list):
        fixed_images = []
        for img in images:
            if isinstance(img, str) and img.startswith('DATA/'):
                fixed_images.append(img.replace('DATA/', IMAGE_BASE_PATH + '/'))
            else:
                fixed_images.append(img)
        return fixed_images
    
    return images

def process_dataset_for_visualization(data):
    """处理数据集，转换格式以便可视化"""
    processed_data = []
    
    for item in data:
        processed_item = item.copy()
        
        # 处理 messages 列（sharegpt格式）
        if 'messages' in processed_item:
            messages = processed_item['messages']
            q_text, a_text = process_sharegpt_messages(messages)
            
            if q_text or a_text:
                processed_item['Q'] = q_text
                processed_item['A'] = a_text
            
            # 保留原始messages供参考，但移到最后
            processed_item['original_messages'] = processed_item.pop('messages')
        
        # 处理 conversations 列（也可能是sharegpt格式）
        if 'conversations' in processed_item:
            conversations = processed_item['conversations']
            q_text, a_text = process_sharegpt_messages(conversations)
            
            if q_text or a_text:
                processed_item['Q'] = q_text
                processed_item['A'] = a_text
            
            # 保留原始conversations供参考
            processed_item['original_conversations'] = processed_item.pop('conversations')
        
        # 处理图片路径 - 特别处理images列表
        if 'images' in processed_item:
            images = processed_item['images']
            if isinstance(images, list) and len(images) > 0:
                # 如果是列表，取第一个图片并修复路径
                first_image = images[0]
                if isinstance(first_image, str) and first_image.startswith('DATA/'):
                    fixed_path = first_image.replace('DATA/', IMAGE_BASE_PATH + '/')
                    processed_item['images'] = fixed_path  # 转换为单个字符串而不是列表
                elif isinstance(first_image, str):
                    processed_item['images'] = first_image
                else:
                    processed_item['images'] = str(first_image)
                
                # 如果有多个图片，保存原始列表作为参考
                if len(images) > 1:
                    fixed_images = []
                    for img in images:
                        if isinstance(img, str) and img.startswith('DATA/'):
                            fixed_images.append(img.replace('DATA/', IMAGE_BASE_PATH + '/'))
                        else:
                            fixed_images.append(img)
                    processed_item['all_images'] = fixed_images
            else:
                processed_item['images'] = fix_image_paths(images)
        
        if 'image' in processed_item:
            processed_item['image'] = fix_image_paths(processed_item['image'])
        
        # 检查其他可能包含图片路径的字段
        for key, value in processed_item.items():
            if key in ['images', 'all_images']:  # 跳过已经处理的字段
                continue
                
            if isinstance(value, str) and value.startswith('DATA/'):
                processed_item[key] = value.replace('DATA/', IMAGE_BASE_PATH + '/')
            elif isinstance(value, list):
                # 检查列表中是否有图片路径
                updated_list = []
                for v in value:
                    if isinstance(v, str) and v.startswith('DATA/'):
                        updated_list.append(v.replace('DATA/', IMAGE_BASE_PATH + '/'))
                    else:
                        updated_list.append(v)
                processed_item[key] = updated_list
        
        processed_data.append(processed_item)
    
    return processed_data

def get_dataset_name_from_filename(filename):
    """从文件名中提取数据集名称和源文件名"""
    # 文件名格式: {dataset_name}_{source_filename}_samples.json
    if filename.endswith('_samples.json'):
        name_part = filename[:-13]  # 去掉 '_samples.json'
        
        # 寻找第一个下划线后的部分作为源文件名
        if '_' in name_part:
            parts = name_part.split('_', 1)
            dataset_name = parts[0]
            source_name = parts[1]
            return dataset_name, source_name
    
    return 'unknown', filename

def load_sampled_data():
    """加载所有采样数据文件"""
    data_files = {}
    
    # 查找所有采样数据文件
    json_files = glob.glob(os.path.join(INPUT_DIR, "*_samples.json"))
    
    for file_path in json_files:
        filename = os.path.basename(file_path)
        dataset_name, source_name = get_dataset_name_from_filename(filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 处理数据格式
            processed_data = process_dataset_for_visualization(data)
            
            # 使用完整的filename作为key以确保唯一性
            file_key = filename.replace('_samples.json', '')
            
            data_files[file_key] = {
                'data': processed_data,
                'file_path': file_path,
                'count': len(processed_data),
                'dataset_name': dataset_name,
                'source_name': source_name,
                'filename': filename
            }
            print(f"已加载并处理 {file_key}: {len(processed_data)} 条数据")
        except Exception as e:
            print(f"加载文件失败 {file_path}: {e}")
    
    return data_files

def generate_html_visualization(data_files):
    """生成HTML可视化文件"""
    try:
        from json_viz.core import JsonVisualizer
    except ImportError:
        print("错误: 无法导入 json_viz")
        return
    
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 为每个数据文件生成单独的可视化文件
    for file_key, file_info in data_files.items():
        try:
            print(f"正在为 {file_key} 生成可视化...")
            
            # 创建临时JSON文件以供JsonVisualizer使用
            temp_json_file = os.path.join(OUTPUT_DIR, f"temp_{file_key}.json")
            
            # 限制显示的样本数量以提高性能
            display_data = file_info['data'][:50] if len(file_info['data']) > 50 else file_info['data']
            
            # 写入临时JSON文件
            with open(temp_json_file, 'w', encoding='utf-8') as f:
                json.dump(display_data, f, ensure_ascii=False, indent=2)
            
            # 设置输出文件路径
            output_file = os.path.join(OUTPUT_DIR, f"{file_key}_visualization.html")
            
            # 定义文本列和图片列
            textual_cols = ['Q', 'A', 'conversations', 'text', 'content', 'answer', 'question', 'instruction', 'output']
            
            # 使用JsonVisualizer生成可视化
            JsonVisualizer.visualize(
                input_file=temp_json_file,
                output_file=output_file,
                title=f"数据集可视化: {file_info['dataset_name']} - {file_info['source_name']} ({len(display_data)}条)",
                textual_cols=textual_cols
            )
            
            # 删除临时文件
            os.remove(temp_json_file)
            
            print(f"已生成可视化文件: {output_file}")
            
        except Exception as e:
            print(f"为 {file_key} 生成可视化时出错: {e}")
            # 清理临时文件
            temp_json_file = os.path.join(OUTPUT_DIR, f"temp_{file_key}.json")
            if os.path.exists(temp_json_file):
                os.remove(temp_json_file)
    
    # 生成总览页面
    generate_overview_page(data_files)

def generate_overview_page(data_files):
    """生成数据集总览页面"""
    html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>医疗数据集采样总览 - 单独文件版本</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #3498db;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .stat-label {{
            color: #7f8c8d;
            margin-top: 5px;
        }}
        .dataset-section {{
            margin-bottom: 40px;
        }}
        .dataset-title {{
            font-size: 1.5em;
            color: #2c3e50;
            margin-bottom: 20px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .files-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 15px;
        }}
        .file-card {{
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
            background: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .file-header {{
            background: #34495e;
            color: white;
            padding: 12px;
            font-weight: bold;
            font-size: 0.9em;
        }}
        .file-content {{
            padding: 12px;
        }}
        .file-count {{
            color: #3498db;
            font-size: 1.1em;
            font-weight: bold;
        }}
        .view-link {{
            display: inline-block;
            margin-top: 8px;
            padding: 6px 12px;
            background: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s;
            font-size: 0.9em;
        }}
        .view-link:hover {{
            background: #2980b9;
        }}
        .timestamp {{
            text-align: center;
            color: #7f8c8d;
            margin-top: 30px;
            font-size: 0.9em;
        }}
        .note {{
            background-color: #e8f4fd;
            border: 1px solid #bee5eb;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
            color: #0c5460;
        }}
        .feature-list {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
        }}
        .feature-list h3 {{
            margin-top: 0;
            color: #495057;
        }}
        .feature-list ul {{
            margin-bottom: 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>医疗数据集采样总览 - 单独文件版本</h1>
        
        <div class="note">
            <strong>说明:</strong> 本页面展示了从各个医疗数据集中采样的数据，每个源文件单独显示。
            每个文件采样了最多10条记录（如果源文件数据不足10条则全部采样），数据已经过处理，
            sharegpt格式的对话被转换为Q&A格式，图片路径已修正。
        </div>
        
        <div class="feature-list">
            <h3>🔧 数据处理功能</h3>
            <ul>
                <li><strong>单独文件处理</strong>: 每个源文件单独生成采样文件和可视化</li>
                <li><strong>对话格式转换</strong>: messages/conversations列自动转换为Q和A列</li>
                <li><strong>图片路径修正</strong>: DATA/路径自动替换为实际路径</li>
                <li><strong>交互式表格</strong>: 支持搜索、排序、列切换</li>
                <li><strong>图片显示</strong>: 自动识别和显示images列中的图片</li>
            </ul>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{total_datasets}</div>
                <div class="stat-label">数据集类别</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_files}</div>
                <div class="stat-label">源文件数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_samples}</div>
                <div class="stat-label">总样本数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{avg_samples:.1f}</div>
                <div class="stat-label">平均每文件样本数</div>
            </div>
        </div>
        
        {dataset_sections}
        
        <div class="timestamp">
            生成时间: {timestamp}
        </div>
    </div>
</body>
</html>
"""
    
    # 按数据集分组
    datasets = {}
    for file_key, file_info in data_files.items():
        dataset_name = file_info['dataset_name']
        if dataset_name not in datasets:
            datasets[dataset_name] = []
        datasets[dataset_name].append(file_info)
    
    # 计算统计信息
    total_datasets = len(datasets)
    total_files = len(data_files)
    total_samples = sum(info['count'] for info in data_files.values())
    avg_samples = total_samples / total_files if total_files > 0 else 0
    
    # 生成数据集部分
    dataset_sections = []
    for dataset_name, files in datasets.items():
        files_html = []
        for file_info in files:
            file_key = file_info['filename'].replace('_samples.json', '')
            card_html = f"""
                <div class="file-card">
                    <div class="file-header">{file_info['source_name']}</div>
                    <div class="file-content">
                        <div class="file-count">{file_info['count']} 条样本</div>
                        <p style="margin: 5px 0; font-size: 0.8em; color: #666;">
                            文件: {file_info['filename']}
                        </p>
                        <a href="{file_key}_visualization.html" class="view-link">查看可视化</a>
                    </div>
                </div>
            """
            files_html.append(card_html)
        
        section_html = f"""
            <div class="dataset-section">
                <div class="dataset-title">{dataset_name} ({len(files)} 个文件)</div>
                <div class="files-grid">
                    {''.join(files_html)}
                </div>
            </div>
        """
        dataset_sections.append(section_html)
    
    # 生成完整HTML
    from datetime import datetime
    html_content = html_template.format(
        total_datasets=total_datasets,
        total_files=total_files,
        total_samples=total_samples,
        avg_samples=avg_samples,
        dataset_sections=''.join(dataset_sections),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # 保存总览文件
    overview_file = os.path.join(OUTPUT_DIR, "index.html")
    with open(overview_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"已生成总览页面: {overview_file}")

def main():
    """主函数"""
    print("开始生成数据可视化（单独文件版本）...")
    
    # 检查json_viz是否可用
    if not check_json_viz():
        return
    
    # 加载采样数据
    data_files = load_sampled_data()
    
    if not data_files:
        print("错误: 未找到采样数据文件")
        print(f"请确保先运行 0_sample_data_individual.py 生成采样数据到 {INPUT_DIR}")
        return
    
    # 生成可视化
    generate_html_visualization(data_files)
    
    print(f"\n可视化生成完成!")
    print(f"可视化文件保存在: {OUTPUT_DIR}")
    print(f"请打开 {os.path.join(OUTPUT_DIR, 'index.html')} 查看总览")

if __name__ == "__main__":
    main() 