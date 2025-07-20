"""
内容过滤器 - 处理消息内容过滤
"""

import re
import logging
from typing import Dict, List, Optional


class MessageFilter:
    """消息过滤器"""
    
    def __init__(self, settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        
        # 预编译正则表达式
        self._compile_patterns()
        
        # 广告关键词
        self.ad_keywords = [
            '广告', '推广', '代理', '加微信', '加QQ', '联系方式', 
            '免费领取', '限时优惠', '立即购买', '点击链接',
            '扫码', '二维码', '客服', '咨询', '代办', '包过',
            '兼职', '刷单', '投资', '理财', '贷款', '博彩',
            '彩票', '赌博', '色情', '成人', '约炮', '一夜情',
            '代孕', '药品', '减肥', '丰胸', '壮阳', '假证',
            '发票', '***', '微商', '淘宝客', '返利'
        ]
        
        # 特殊符号（保留#号）
        self.special_chars_pattern = re.compile(r'[^\w\s\u4e00-\u9fff#]', re.UNICODE)
        
        # 表情符号（保留#号）
        self.emoji_pattern = re.compile(
            r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\U0001f900-\U0001f9ff\U0001f600-\U0001f64f\U0001f680-\U0001f6ff\u2600-\u27bf]',
            re.UNICODE
        )

    def _compile_patterns(self):
        """预编译正则表达式"""
        # URL链接匹配
        self.url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            re.IGNORECASE
        )
        
        # Telegram链接
        self.telegram_link_pattern = re.compile(
            r'(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/\S+',
            re.IGNORECASE
        )
        
        # @提及
        self.mention_pattern = re.compile(r'@\w+')
        
        # 电话号码
        self.phone_pattern = re.compile(r'(?:\+86)?1[3-9]\d{9}')
        
        # QQ号
        self.qq_pattern = re.compile(r'[Qq]{2}[:：\s]*[0-9]{5,12}')
        
        # 微信号
        self.wechat_pattern = re.compile(r'[微V信]{1,2}[:：\s]*[a-zA-Z0-9_-]{6,20}')

    def filter_text(self, text: str, filters: Dict) -> str:
        """过滤文本内容"""
        if not text:
            return ""
        
        try:
            filtered_text = text
            
            # 广告检测
            if filters.get('ad_detection', False):
                if self._is_advertisement(filtered_text):
                    return ""
            
            # 智能过滤
            if filters.get('smart_filter', False):
                if self._is_spam_content(filtered_text):
                    return ""
            
            # 删除链接
            if filters.get('remove_links', False):
                filtered_text = self._remove_links(filtered_text)
            
            # 删除表情符号
            if filters.get('remove_emojis', False):
                filtered_text = self._remove_emojis(filtered_text)
            
            # 删除特殊符号
            if filters.get('remove_special_chars', False):
                filtered_text = self._remove_special_chars(filtered_text)
            
            # 自定义过滤规则
            custom_rules = filters.get('custom_rules', [])
            if custom_rules:
                filtered_text = self._apply_custom_rules(filtered_text, custom_rules)
            
            # 清理多余空行
            filtered_text = self._clean_whitespace(filtered_text)
            
            return filtered_text.strip()
            
        except Exception as e:
            self.logger.error(f"❌ 过滤文本失败: {e}")
            return text

    def _is_advertisement(self, text: str) -> bool:
        """检测是否为广告内容"""
        try:
            text_lower = text.lower()
            
            # 检查广告关键词
            ad_count = sum(1 for keyword in self.ad_keywords if keyword in text_lower)
            
            # 如果包含2个或以上广告关键词，认为是广告
            if ad_count >= 2:
                return True
            
            # 检查联系方式
            contact_patterns = [
                self.phone_pattern,
                self.qq_pattern,
                self.wechat_pattern
            ]
            
            contact_count = sum(1 for pattern in contact_patterns if pattern.search(text))
            
            # 包含联系方式且有广告关键词
            if contact_count > 0 and ad_count > 0:
                return True
            
            # 检查典型广告短语
            ad_phrases = [
                '加我微信', '联系客服', '免费咨询', '立即下单',
                '扫码关注', '点击购买', '限时特价', '包邮到家'
            ]
            
            phrase_count = sum(1 for phrase in ad_phrases if phrase in text)
            if phrase_count >= 2:
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 广告检测失败: {e}")
            return False

    def _is_spam_content(self, text: str) -> bool:
        """检测是否为垃圾内容"""
        try:
            # 检查重复字符
            if len(set(text)) / len(text) < 0.3 and len(text) > 10:
                return True
            
            # 检查过多感叹号或问号
            if text.count('!') + text.count('！') + text.count('?') + text.count('？') > len(text) * 0.2:
                return True
            
            # 检查全大写英文（超过一定比例）
            english_chars = re.findall(r'[a-zA-Z]', text)
            if len(english_chars) > 10:
                upper_ratio = sum(1 for c in english_chars if c.isupper()) / len(english_chars)
                if upper_ratio > 0.8:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 垃圾内容检测失败: {e}")
            return False

    def _remove_links(self, text: str) -> str:
        """删除链接"""
        try:
            # 删除HTTP链接
            text = self.url_pattern.sub('', text)
            
            # 删除Telegram链接
            text = self.telegram_link_pattern.sub('', text)
            
            # 删除@提及
            text = self.mention_pattern.sub('', text)
            
            return text
            
        except Exception as e:
            self.logger.error(f"❌ 删除链接失败: {e}")
            return text

    def _remove_emojis(self, text: str) -> str:
        """删除表情符号（保留#号）"""
        try:
            return self.emoji_pattern.sub('', text)
        except Exception as e:
            self.logger.error(f"❌ 删除表情符号失败: {e}")
            return text

    def _remove_special_chars(self, text: str) -> str:
        """删除特殊符号（保留#号）"""
        try:
            return self.special_chars_pattern.sub('', text)
        except Exception as e:
            self.logger.error(f"❌ 删除特殊符号失败: {e}")
            return text

    def _apply_custom_rules(self, text: str, rules: List[Dict]) -> str:
        """应用自定义过滤规则"""
        try:
            for rule in rules:
                rule_type = rule.get('type')
                pattern = rule.get('pattern')
                replacement = rule.get('replacement', '')
                
                if not pattern:
                    continue
                
                if rule_type == 'regex':
                    # 正则表达式替换
                    text = re.sub(pattern, replacement, text)
                elif rule_type == 'keyword':
                    # 关键词替换
                    text = text.replace(pattern, replacement)
                elif rule_type == 'remove_line':
                    # 删除包含关键词的整行
                    lines = text.split('\n')
                    lines = [line for line in lines if pattern not in line]
                    text = '\n'.join(lines)
            
            return text
            
        except Exception as e:
            self.logger.error(f"❌ 应用自定义规则失败: {e}")
            return text

    def _clean_whitespace(self, text: str) -> str:
        """清理多余空白字符"""
        try:
            # 删除多余空行
            lines = text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line = line.strip()
                if line or (cleaned_lines and cleaned_lines[-1]):
                    cleaned_lines.append(line)
            
            # 删除末尾空行
            while cleaned_lines and not cleaned_lines[-1]:
                cleaned_lines.pop()
            
            return '\n'.join(cleaned_lines)
            
        except Exception as e:
            self.logger.error(f"❌ 清理空白字符失败: {e}")
            return text

    def test_filter(self, text: str, filters: Dict) -> Dict[str, str]:
        """测试过滤效果"""
        try:
            original = text
            filtered = self.filter_text(text, filters)
            
            return {
                'original': original,
                'filtered': filtered,
                'removed': len(original) - len(filtered),
                'filters_applied': list(filters.keys())
            }
            
        except Exception as e:
            self.logger.error(f"❌ 测试过滤失败: {e}")
            return {
                'original': text,
                'filtered': text,
                'removed': 0,
                'filters_applied': [],
                'error': str(e)
            }

    def get_filter_stats(self, text: str) -> Dict[str, int]:
        """获取文本统计信息"""
        try:
            stats = {
                'total_chars': len(text),
                'total_words': len(text.split()),
                'total_lines': len(text.split('\n')),
                'urls': len(self.url_pattern.findall(text)),
                'mentions': len(self.mention_pattern.findall(text)),
                'phones': len(self.phone_pattern.findall(text)),
                'qq_numbers': len(self.qq_pattern.findall(text)),
                'wechat_ids': len(self.wechat_pattern.findall(text)),
                'emojis': len(self.emoji_pattern.findall(text)),
                'ad_keywords': sum(1 for keyword in self.ad_keywords if keyword in text.lower())
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ 获取文本统计失败: {e}")
            return {}

    def update_ad_keywords(self, keywords: List[str]):
        """更新广告关键词列表"""
        try:
            self.ad_keywords.extend(keywords)
            # 去重
            self.ad_keywords = list(set(self.ad_keywords))
            self.logger.info(f"📝 广告关键词已更新，当前数量: {len(self.ad_keywords)}")
            
        except Exception as e:
            self.logger.error(f"❌ 更新广告关键词失败: {e}")

    def get_ad_keywords(self) -> List[str]:
        """获取广告关键词列表"""
        return self.ad_keywords.copy()