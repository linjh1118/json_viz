#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据采样脚本
从 data_readme.sh 中定义的各种数据集中采样小部分数据，存放到 input 文件夹
"""

import json
import os
import random
import ast
from pathlib import Path
from typing import Dict, List, Any

# 设置随机种子以确保可重现性
random.seed(42)

# 配置
INPUT_DIR = "/mnt/bn/med-mllm-lfv2/linjh/project/med_vlm_rl/code/0609_difficulty/input"
SAMPLE_SIZE_PER_DATASET = 10  # 每个数据集采样的样本数量

# 从 data_readme.sh 中提取的数据集配置
DATASETS_CONFIG = {
    "type_a": {
        "a1.json": 1.0,
        "a2.json": 1.0,
        "a3.json": 1.0,
        "a4.json": 1.0,
        "a5.json": 1.0,
        "a6.json": 1.0,
        "a7.json": 1.0,
    },
    "type_b": {
        "b1.json": 1.0,
        "b2.json": 1.0,
        "b3.json": 1.0,
        "b4.json": 1.0,
        "b5.json": 1.0,
        "b6.json": 1.0,
        "b7.json": 1.0,
    },
    "type_c": {
        "c1.json": 1.0,
        "c2.json": 1.0,
        "c3.json": 1.0,
        "c4.json": 1.0,
        "c5.json": 1.0,
        "c6.json": 1.0,
        "c7.json": 1.0,
    },
    "type_d": {
        "d1.json": 1.0,
        "d2.json": 1.0,
        "d3.json": 1.0,
        "d4.json": 1.0,
        "d5.json": 1.0,
        "d6.json": 1.0,
        "d7.json": 1.0,
    }
}

def load_json_safely(file_path: str) -> List[Dict[str, Any]]:
    """安全地加载JSON文件"""
    try:
        if not os.path.exists(file_path):
            print(f"Warning: 文件不存在: {file_path}")
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 确保返回的是列表格式
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            print(f"Warning: 不支持的数据格式 in {file_path}")
            return []
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return []

def sample_data_from_file(file_path: str, sample_size: int) -> List[Dict[str, Any]]:
    """从单个文件中采样数据"""
    data = load_json_safely(file_path)
    if not data:
        return []
    
    # 如果数据量小于采样大小，返回全部数据
    if len(data) <= sample_size:
        return data
    
    # 随机采样
    return random.sample(data, sample_size)

def save_sampled_data(data: List[Dict[str, Any]], output_path: str):
    """保存采样后的数据"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"已保存 {len(data)} 条数据到: {output_path}")

def main():
    """主函数"""
    print("开始数据采样...")
    
    # 确保输出目录存在
    os.makedirs(INPUT_DIR, exist_ok=True)
    
    total_samples = 0
    
    # 遍历每个数据集类别
    for dataset_name, dataset_files in DATASETS_CONFIG.items():
        print(f"\n处理数据集类别: {dataset_name}")
        
        category_samples = []
        
        # 遍历该类别下的每个文件
        for file_path, weight in dataset_files.items():
            print(f"  处理文件: {os.path.basename(file_path)}")
            
            # 采样数据
            samples = sample_data_from_file(file_path, SAMPLE_SIZE_PER_DATASET)
            
            # 为每个样本添加来源信息
            for sample in samples:
                sample['source_file'] = file_path
                sample['source_dataset'] = dataset_name
                sample['weight'] = weight
            
            category_samples.extend(samples)
        
        # 保存该类别的采样数据
        if category_samples:
            output_path = os.path.join(INPUT_DIR, f"{dataset_name}_samples.json")
            save_sampled_data(category_samples, output_path)
            total_samples += len(category_samples)
    
    print(f"\n数据采样完成! 总计采样了 {total_samples} 条数据")
    print(f"采样数据保存在: {INPUT_DIR}")

if __name__ == "__main__":
    main()
