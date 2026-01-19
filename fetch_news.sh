#!/bin/bash
# ==============================================================================
# HSE资讯自动抓取脚本 - Bash版
# 功能：从RSSHub抓取今日头条安环管理类文章
# 版本：V1.0
# ==============================================================================

set -e

# 配置
KEYWORDS=("施工管理" "安全管理" "环境保护管理" "安全生产" "工程事故")
REPORT="output/daily_summary.md"
RAW_DIR="output/raw"
MAX_ITEMS_PER_KEYWORD=15

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 创建输出目录
mkdir -p output/raw

# 日期
TODAY=$(date +'%Y-%m-%d')
echo -e "${GREEN}🚀 HSE资讯抓取系统启动 - $TODAY${NC}"

# 初始化报告
cat > $REPORT << EOF
# 📰 今日头条安环管理热文汇总

**日期**: $TODAY  
**生成时间**: $(date +'%H:%M:%S')  
**关键词**: ${KEYWORDS[*]}

---

EOF

# 汇总所有新闻数据
ALL_NEWS=""

for kw in "${KEYWORDS[@]}"; do
    echo -e "${YELLOW}📡 正在检索: $kw ...${NC}"
    
    # URL编码关键词
    ENCODED_KW=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$kw'))")
    
    # 使用 RSSHub 抓取今日头条搜索结果
    # 备选源: rsshub.app, rsshub.rssforever.com
    RSSHUB_URL="https://rsshub.app/toutiao/search/${ENCODED_KW}"
    
    RAW_FILE="${RAW_DIR}/${kw}_raw.xml"
    
    # 抓取RSS数据
    if curl -s --connect-timeout 10 -o "$RAW_FILE" "$RSSHUB_URL"; then
        # 检查是否有效XML
        if head -1 "$RAW_FILE" | grep -q "<?xml"; then
            echo -e "${GREEN}  ✓ 成功获取 $kw 数据${NC}"
            
            # 提取标题和链接 (使用xmlstarlet或xmllint)
            if command -v xmlstarlet &> /dev/null; then
                NEWS_DATA=$(xmlstarlet sel -t -m "//item" \
                    -v "concat(title, '|||', link, '|||', pubDate)" -n "$RAW_FILE" 2>/dev/null | head -$MAX_ITEMS_PER_KEYWORD)
            else
                # 备选：使用grep/sed简单提取
                NEWS_DATA=$(grep -oP '(?<=<title>).*?(?=</title>)' "$RAW_FILE" | head -$MAX_ITEMS_PER_KEYWORD)
            fi
            
            ALL_NEWS+="## 关键词: $kw\n$NEWS_DATA\n\n"
        else
            echo -e "${RED}  ✗ $kw 返回数据无效${NC}"
        fi
    else
        echo -e "${RED}  ✗ 无法连接 RSSHub${NC}"
    fi
    
    # 礼貌延迟
    sleep 2
done

# 保存原始汇总
echo -e "$ALL_NEWS" > "${RAW_DIR}/all_news.txt"

echo -e "${GREEN}📝 原始数据已保存到 ${RAW_DIR}/${NC}"
echo -e "${YELLOW}➡️  请运行 Python 脚本调用 Gemini 进行智能筛选${NC}"

# 统计
TOTAL_LINES=$(wc -l < "${RAW_DIR}/all_news.txt" 2>/dev/null || echo "0")
echo -e "${GREEN}✅ 抓取完成！共获取约 $TOTAL_LINES 条记录${NC}"
