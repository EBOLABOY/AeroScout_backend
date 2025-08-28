#!/bin/bash

# 数据分析工具脚本
# 帮助用户快速分析保存的数据对比文件

DATA_DIR="./data_analysis"

show_usage() {
    echo "📊 数据分析工具 - TicketRadar"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  list      列出所有数据对比文件"
    echo "  latest    显示最新文件的统计信息"
    echo "  summary   显示所有文件的压缩率统计"
    echo "  view      查看指定文件的详细信息"
    echo "  clean     清理7天前的旧文件"
    echo "  help      显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 list"
    echo "  $0 latest"
    echo "  $0 view data_comparison_20250828_143025.json"
}

list_files() {
    echo "📁 数据对比文件列表:"
    if [ ! -d "$DATA_DIR" ]; then
        echo "❌ 数据分析目录不存在: $DATA_DIR"
        return 1
    fi
    
    files=$(find "$DATA_DIR" -name "data_comparison_*.json" -type f 2>/dev/null | sort -r)
    
    if [ -z "$files" ]; then
        echo "📭 暂无数据对比文件"
        echo "💡 提示: 执行航班搜索后将自动生成对比文件"
        return 0
    fi
    
    count=0
    for file in $files; do
        filename=$(basename "$file")
        size=$(du -h "$file" | cut -f1)
        timestamp=$(echo "$filename" | grep -o '[0-9]\{8\}_[0-9]\{6\}' | sed 's/_/ /')
        echo "  📄 $filename ($size) - $timestamp"
        count=$((count + 1))
    done
    
    echo ""
    echo "📊 总计: $count 个文件"
}

show_latest() {
    latest_file=$(find "$DATA_DIR" -name "data_comparison_*.json" -type f 2>/dev/null | sort -r | head -n1)
    
    if [ -z "$latest_file" ]; then
        echo "❌ 未找到数据对比文件"
        return 1
    fi
    
    echo "📊 最新文件统计信息:"
    echo "📄 文件: $(basename "$latest_file")"
    echo "📅 大小: $(du -h "$latest_file" | cut -f1)"
    
    if command -v jq >/dev/null 2>&1; then
        echo ""
        echo "🔍 内容统计:"
        jq -r '
            .metadata.compression_stats as $stats |
            "📈 压缩率: \($stats.reduction_ratio)%" ,
            "📦 原始数据大小: \($stats.original_size.total_size) 字符" ,
            "🧹 清洗后大小: \($stats.cleaned_size.total_size) 字符" ,
            "" ,
            "✈️  航班数量统计:" ,
            "  • Google Flights: \($stats.original_size.flight_counts.google_flights // 0)" ,
            "  • Kiwi: \($stats.original_size.flight_counts.kiwi_flights // 0)" ,
            "  • AI推荐: \($stats.original_size.flight_counts.ai_flights // 0)"
        ' "$latest_file" 2>/dev/null || echo "⚠️  无法解析JSON内容"
    else
        echo "💡 安装 jq 工具可查看详细统计信息: apt-get install jq"
    fi
}

show_summary() {
    echo "📈 所有文件压缩率统计:"
    files=$(find "$DATA_DIR" -name "data_comparison_*.json" -type f 2>/dev/null | sort -r)
    
    if [ -z "$files" ]; then
        echo "❌ 未找到数据对比文件"
        return 1
    fi
    
    if ! command -v jq >/dev/null 2>&1; then
        echo "❌ 需要安装 jq 工具: apt-get install jq"
        return 1
    fi
    
    echo "📊 文件名                          | 压缩率    | 原始大小  | 航班总数"
    echo "────────────────────────────────────┼───────────┼───────────┼─────────"
    
    total_files=0
    total_reduction=0
    
    for file in $files; do
        filename=$(basename "$file" | cut -c1-30)
        stats=$(jq -r '.metadata.compression_stats | "\(.reduction_ratio)|\(.original_size.total_size)|\((.original_size.flight_counts.google_flights // 0) + (.original_size.flight_counts.kiwi_flights // 0) + (.original_size.flight_counts.ai_flights // 0))"' "$file" 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            IFS='|' read -r reduction original_size flight_count <<< "$stats"
            printf "%-30s | %7.1f%% | %8s | %8s\n" "$filename" "$reduction" "$original_size" "$flight_count"
            total_files=$((total_files + 1))
            total_reduction=$(echo "$total_reduction + $reduction" | bc -l 2>/dev/null || echo "$total_reduction")
        fi
    done
    
    if command -v bc >/dev/null 2>&1 && [ "$total_files" -gt 0 ]; then
        avg_reduction=$(echo "scale=1; $total_reduction / $total_files" | bc -l)
        echo "────────────────────────────────────┼───────────┼───────────┼─────────"
        printf "平均值 (%d个文件)                   | %7.1f%% |           |\n" "$total_files" "$avg_reduction"
    fi
}

view_file() {
    if [ -z "$1" ]; then
        echo "❌ 请指定文件名"
        echo "💡 使用 '$0 list' 查看可用文件"
        return 1
    fi
    
    filepath="$DATA_DIR/$1"
    if [ ! -f "$filepath" ]; then
        echo "❌ 文件不存在: $filepath"
        return 1
    fi
    
    if command -v jq >/dev/null 2>&1; then
        echo "📄 文件详细信息: $1"
        echo ""
        jq -r '
            .metadata as $meta |
            "📅 时间戳: " + $meta.timestamp ,
            "🔍 搜索参数:" ,
            "  出发地: " + $meta.search_params.departure_code ,
            "  目的地: " + $meta.search_params.destination_code ,
            "  日期: " + $meta.search_params.depart_date ,
            "  乘客: " + ($meta.search_params.adults | tostring) + "人" ,
            "" ,
            "📊 压缩统计:" ,
            "  压缩率: " + ($meta.compression_stats.reduction_ratio | tostring) + "%" ,
            "  原始大小: " + ($meta.compression_stats.original_size.total_size | tostring) + " 字符" ,
            "  清洗后: " + ($meta.compression_stats.cleaned_size.total_size | tostring) + " 字符"
        ' "$filepath" 2>/dev/null || echo "⚠️  无法解析JSON内容"
    else
        echo "💡 安装 jq 工具可查看详细信息: apt-get install jq"
        echo "📄 文件大小: $(du -h "$filepath" | cut -f1)"
    fi
}

clean_old_files() {
    echo "🧹 清理7天前的旧文件..."
    
    if [ ! -d "$DATA_DIR" ]; then
        echo "❌ 数据分析目录不存在: $DATA_DIR"
        return 1
    fi
    
    deleted_count=0
    find "$DATA_DIR" -name "data_comparison_*.json" -type f -mtime +7 -print0 2>/dev/null | while IFS= read -r -d '' file; do
        echo "🗑️  删除: $(basename "$file")"
        rm "$file"
        deleted_count=$((deleted_count + 1))
    done
    
    echo "✅ 清理完成，删除了 $deleted_count 个旧文件"
}

# 主程序
case "$1" in
    "list")
        list_files
        ;;
    "latest")
        show_latest
        ;;
    "summary")
        show_summary
        ;;
    "view")
        view_file "$2"
        ;;
    "clean")
        clean_old_files
        ;;
    "help"|"")
        show_usage
        ;;
    *)
        echo "❌ 未知命令: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac