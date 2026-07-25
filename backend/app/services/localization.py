"""部署配置檔共用的顯示格式。

配置檔是部署級別設定，不提供使用者切換。這個模組只處理純格式化，避免 API、
匯出與排課報告各自複製一套學年標籤規則。
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings

ROLE_DISPLAY_NAMES: dict[str, dict[str, str]] = {
    "tw_k12": {
        "admin": "系統管理員",
        "director": "教務主任",
        "scheduler": "教學組長",
        "teacher": "教師",
    },
    "cn_mainland": {
        "admin": "系统管理员",
        "director": "教务主任",
        "scheduler": "教务员",
        "teacher": "教师",
    },
}

TERMS: dict[str, dict[str, str]] = {
    "tw_k12": {
        "system_name": "排課與調代課系統",
        "school_calendar": "校曆",
        "substitute": "代課",
        "swap": "調課",
        "leave": "請假",
    },
    "cn_mainland": {
        "system_name": "排课与调代课系统",
        "school_calendar": "校历",
        "substitute": "代课",
        "swap": "调课",
        "leave": "请假",
    },
}

# Values persisted in the database stay stable English identifiers.  These maps
# are intentionally here, rather than alongside the ORM enums, because they are
# presentation data and must follow the deployment profile.
DISPLAY_LABELS: dict[str, dict[str, dict[str, str]]] = {
    "tw_k12": {
        "leave_type": {
            "official": "公假",
            "personal": "事假",
            "sick": "病假",
            "marriage": "婚假",
            "bereavement": "喪假",
            "maternity": "產假",
            "training": "進修",
        },
        "affected_status": {
            "pending": "待處理",
            "resolved": "已處置",
            "completed": "已完成",
            "cancelled": "已取消",
        },
        "substitution_type": {
            "substitute": "代課",
            "swap": "調課",
            "merge": "併班",
            "self_study": "自習",
            "cancel": "不處理",
        },
        "export": {
            "timetable": "課表",
            "period": "節次",
            "printed_on": "列印日",
            "school_timetable": "全校課表總表",
            "class_timetables": "全校班級課表",
            "summary": "彙總",
            "detail": "明細",
            "teacher": "教師",
            "date": "日期",
            "class": "班級",
            "subject": "科目",
            "absent_teacher": "原任教師",
            "leave_type": "假別",
            "disposition": "處置",
            "billable": "計費",
            "funding_source": "經費來源",
            "substitution_periods": "代課節數",
            "billable_periods": "計費節數",
            "yes": "是",
            "no": "否",
        },
    },
    "cn_mainland": {
        "leave_type": {
            "official": "公假",
            "personal": "事假",
            "sick": "病假",
            "marriage": "婚假",
            "bereavement": "丧假",
            "maternity": "产假",
            "training": "进修",
        },
        "affected_status": {
            "pending": "待处理",
            "resolved": "已处置",
            "completed": "已完成",
            "cancelled": "已取消",
        },
        "substitution_type": {
            "substitute": "代课",
            "swap": "调课",
            "merge": "合班",
            "self_study": "自习",
            "cancel": "不处理",
        },
        "export": {
            "timetable": "课表",
            "period": "节次",
            "printed_on": "打印日期",
            "school_timetable": "全校课表总表",
            "class_timetables": "全校班级课表",
            "summary": "汇总",
            "detail": "明细",
            "teacher": "教师",
            "date": "日期",
            "class": "班级",
            "subject": "科目",
            "absent_teacher": "原任教师",
            "leave_type": "假别",
            "disposition": "处置",
            "billable": "计费",
            "funding_source": "经费来源",
            "substitution_periods": "代课节数",
            "billable_periods": "计费节数",
            "yes": "是",
            "no": "否",
        },
    },
}

WEEKDAY_NAMES: dict[str, tuple[str, ...]] = {
    "tw_k12": ("週一", "週二", "週三", "週四", "週五", "週六", "週日"),
    "cn_mainland": ("周一", "周二", "周三", "周四", "周五", "周六", "周日"),
}

PROFILE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "tw_k12": {
        "locale": "zh-TW",
        "language": "繁體中文",
        "timezone": "Asia/Taipei",
        "academic_year_min": 100,
        "academic_year_max": 200,
        "academic_year_format": "{year} 學年度第 {term} 學期",
        "term_labels": {1: "第 1 學期", 2: "第 2 學期"},
    },
    "cn_mainland": {
        "locale": "zh-CN",
        "language": "简体中文",
        "timezone": "Asia/Shanghai",
        "academic_year_min": 1900,
        "academic_year_max": 2100,
        "academic_year_format": "{year}-{next_year}学年{term_label}",
        "term_labels": {1: "第一学期", 2: "第二学期"},
    },
}

# Existing modules predate deployment profiles and therefore still contain
# historical zh-TW error/report sentences.  Keep their domain logic untouched,
# but normalize user-facing text at API/notification boundaries for mainland
# deployments.  Phrase replacements run before character conversion so local
# school terminology is correct rather than merely script-converted.
MAINLAND_PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("教學組長", "教务员"),
    ("學制範本", "学制模板"),
    ("專科教室", "专用教室"),
    ("實習工場", "实训场地"),
    ("學年度", "学年"),
    ("國中", "初中"),
    ("導師", "班主任"),
    ("鐘點", "课时"),
    ("匯入", "导入"),
    ("匯出", "导出"),
    ("列印", "打印"),
    ("還原", "恢复"),
    ("跑班", "走班"),
    ("併班", "合班"),
    ("銷假", "销假"),
    ("假別", "假别"),
    ("節次表", "节次表"),
    ("格位", "单元格"),
    ("存取", "访问"),
    ("起訖", "起止"),
    ("檔案", "文件"),
    ("範本", "模板"),
    ("寄件人", "发件人"),
    ("連接埠", "端口"),
    ("呼叫端", "调用方"),
    ("迴圈", "循环"),
    ("回應", "响应"),
    ("改採", "改用"),
    ("原訂", "原定"),
    ("已封存", "已归档"),
)

TRADITIONAL_TO_SIMPLIFIED = str.maketrans(
    {
        "萬": "万", "與": "与", "專": "专", "業": "业", "叢": "丛", "東": "东",
        "絲": "丝", "兩": "两", "嚴": "严", "喪": "丧", "個": "个", "豐": "丰",
        "臨": "临", "為": "为", "麗": "丽", "舉": "举", "麼": "么", "義": "义",
        "烏": "乌", "樂": "乐", "喬": "乔", "習": "习", "鄉": "乡", "書": "书",
        "買": "买", "亂": "乱", "乾": "干", "爭": "争", "於": "于", "虧": "亏",
        "雲": "云", "亞": "亚", "產": "产", "畝": "亩", "親": "亲", "褻": "亵",
        "億": "亿", "僅": "仅", "僕": "仆", "從": "从", "侖": "仑", "倉": "仓",
        "儀": "仪", "們": "们", "價": "价", "眾": "众", "優": "优", "會": "会",
        "傘": "伞", "偉": "伟", "傳": "传", "傷": "伤", "倫": "伦", "偽": "伪",
        "體": "体", "餘": "余", "俠": "侠", "侶": "侣", "側": "侧", "僑": "侨",
        "儲": "储", "兒": "儿", "兌": "兑", "黨": "党", "蘭": "兰", "關": "关",
        "興": "兴", "養": "养", "獸": "兽", "內": "内", "岡": "冈", "冊": "册",
        "寫": "写", "軍": "军", "農": "农", "馮": "冯", "衝": "冲", "決": "决",
        "況": "况", "凍": "冻", "淨": "净", "準": "准", "涼": "凉", "減": "减",
        "湊": "凑", "幾": "几", "鳳": "凤", "憑": "凭", "凱": "凯", "擊": "击",
        "劃": "划", "劉": "刘", "則": "则", "剛": "刚", "創": "创", "刪": "删",
        "別": "别", "劍": "剑", "劇": "剧", "勸": "劝", "辦": "办", "務": "务",
        "動": "动", "勵": "励", "勞": "劳", "勢": "势", "勳": "勋", "勻": "匀",
        "區": "区", "醫": "医", "華": "华", "協": "协", "單": "单", "賣": "卖",
        "盧": "卢", "衛": "卫", "卻": "却", "廠": "厂", "廳": "厅", "歷": "历",
        "厲": "厉", "壓": "压", "厭": "厌", "廁": "厕", "縣": "县", "參": "参",
        "雙": "双", "發": "发", "變": "变", "敘": "叙", "葉": "叶", "號": "号",
        "嘆": "叹", "嚇": "吓", "呂": "吕", "嗎": "吗", "聽": "听", "啟": "启",
        "吳": "吴", "員": "员", "喚": "唤", "問": "问", "啞": "哑",
        "喲": "哟", "嘍": "喽", "嘗": "尝", "嘯": "啸", "嘩": "哗",
        "噴": "喷", "噸": "吨", "嚀": "咛", "嚨": "咙", "囑": "嘱", "團": "团",
        "園": "园", "國": "国", "圍": "围", "圖": "图", "圓": "圆", "聖": "圣",
        "場": "场", "壞": "坏", "塊": "块", "堅": "坚", "壇": "坛", "墳": "坟",
        "墊": "垫", "塵": "尘", "墜": "坠", "壟": "垄", "壯": "壮", "聲": "声",
        "殼": "壳", "壺": "壶", "處": "处", "備": "备", "複": "复", "夠": "够",
        "頭": "头", "誇": "夸", "夾": "夹", "奪": "夺", "獎": "奖", "奧": "奥",
        "婦": "妇", "媽": "妈", "孫": "孙", "學": "学", "寧": "宁", "寶": "宝",
        "實": "实", "審": "审", "憲": "宪", "宮": "宫", "寬": "宽", "賓": "宾",
        "對": "对", "尋": "寻", "導": "导", "將": "将", "屆": "届", "屬": "属",
        "嶼": "屿", "嶺": "岭", "歲": "岁", "豈": "岂", "崗": "岗", "島": "岛",
        "巖": "岩", "幣": "币", "帥": "帅", "師": "师", "帳": "账", "帶": "带",
        "幫": "帮", "幹": "干", "庫": "库", "應": "应", "廟": "庙",
        "廣": "广", "廢": "废", "開": "开", "異": "异", "棄": "弃", "張": "张",
        "強": "强", "彈": "弹", "彙": "汇", "彎": "弯", "錄": "录", "當": "当",
        "徑": "径", "後": "后", "徹": "彻", "憶": "忆", "懷": "怀",
        "態": "态", "總": "总", "恆": "恒", "戀": "恋", "懇": "恳", "惡": "恶",
        "惱": "恼", "慣": "惯", "願": "愿", "慶": "庆", "憂": "忧", "憤": "愤",
        "懶": "懒", "戲": "戏", "戶": "户", "擁": "拥", "擇": "择", "擋": "挡",
        "撥": "拨", "撫": "抚", "擴": "扩", "擺": "摆", "攔": "拦", "攤": "摊",
        "攪": "搅", "攜": "携", "攝": "摄", "數": "数", "斂": "敛",
        "斃": "毙", "斷": "断", "無": "无", "舊": "旧", "時": "时", "曆": "历",
        "晝": "昼", "顯": "显", "暫": "暂", "術": "术", "樸": "朴", "機": "机",
        "殺": "杀", "雜": "杂", "權": "权", "條": "条", "來": "来", "楊": "杨",
        "極": "极", "構": "构", "標": "标", "樣": "样", "樓": "楼", "樹": "树",
        "橋": "桥", "檔": "档", "檢": "检", "櫃": "柜", "欄": "栏", "歐": "欧",
        "歡": "欢", "歸": "归", "殘": "残", "殲": "歼", "氣": "气",
        "漢": "汉", "湯": "汤", "溝": "沟", "滅": "灭", "滬": "沪", "滿": "满",
        "濃": "浓", "濟": "济", "濕": "湿", "瀏": "浏", "灣": "湾", "燈": "灯",
        "燒": "烧", "燙": "烫", "爐": "炉", "牆": "墙", "獨": "独", "獲": "获",
        "獻": "献", "環": "环", "現": "现", "畫": "画",
        "療": "疗", "盡": "尽", "監": "监", "盤": "盘", "睜": "睁",
        "確": "确", "礎": "础", "禮": "礼", "種": "种", "稱": "称", "穩": "稳",
        "窩": "窝", "窮": "穷", "競": "竞", "筆": "笔", "籤": "签", "簡": "简",
        "節": "节", "篩": "筛", "類": "类", "粵": "粤", "糧": "粮", "糾": "纠",
        "紀": "纪", "約": "约", "紅": "红", "紋": "纹", "納": "纳", "純": "纯",
        "紙": "纸", "級": "级", "紛": "纷", "細": "细", "終": "终", "組": "组",
        "結": "结", "絕": "绝", "統": "统", "綁": "绑", "經": "经", "綜": "综",
        "綠": "绿", "緊": "紧", "線": "线", "練": "练", "縱": "纵",
        "縮": "缩", "績": "绩", "織": "织", "續": "续", "纔": "才", "罰": "罚",
        "罷": "罢", "羅": "罗", "聯": "联", "聰": "聪", "職": "职",
        "聞": "闻", "肅": "肃", "腦": "脑", "腳": "脚", "脫": "脱",
        "臉": "脸", "臺": "台", "艦": "舰",
        "藝": "艺", "藥": "药", "蘇": "苏", "蘋": "苹", "虛": "虚",
        "衆": "众", "補": "补", "裝": "装", "裡": "里", "製": "制",
        "褲": "裤", "見": "见", "規": "规", "覺": "觉", "覽": "览",
        "觀": "观", "觸": "触", "計": "计", "訂": "订", "訊": "讯", "記": "记",
        "討": "讨", "訓": "训", "託": "托", "訪": "访", "設": "设", "許": "许",
        "訴": "诉", "診": "诊", "註": "注", "該": "该", "詳": "详", "誤": "误",
        "說": "说", "課": "课", "調": "调", "談": "谈", "請": "请", "諸": "诸",
        "諾": "诺", "謀": "谋", "謂": "谓", "謝": "谢", "謹": "谨", "證": "证",
        "識": "识", "譯": "译", "議": "议", "護": "护", "讀": "读",
        "讓": "让", "讚": "赞", "貝": "贝", "負": "负", "貢": "贡",
        "財": "财", "責": "责", "敗": "败", "貨": "货", "質": "质", "販": "贩",
        "貪": "贪", "貫": "贯", "貴": "贵", "貸": "贷", "費": "费", "貼": "贴",
        "貿": "贸", "賀": "贺", "賄": "贿", "資": "资", "賊": "贼",
        "賠": "赔", "賢": "贤", "賦": "赋", "賬": "账", "賴": "赖",
        "賺": "赚", "購": "购", "贈": "赠", "趕": "赶", "趙": "赵", "跡": "迹",
        "踐": "践", "蹤": "踪", "躍": "跃", "車": "车", "軌": "轨",
        "軟": "软", "轉": "转", "輪": "轮", "輸": "输", "邊": "边",
        "遷": "迁", "過": "过", "達": "达", "遠": "远", "違": "违", "適": "适",
        "選": "选", "遺": "遗", "鄧": "邓", "鄭": "郑", "鄰": "邻", "郵": "邮",
        "釋": "释", "釐": "厘", "針": "针", "鈴": "铃", "鈔": "钞",
        "鋼": "钢", "錢": "钱", "錯": "错", "錶": "表", "鍋": "锅",
        "鍵": "键", "鎖": "锁", "鎮": "镇", "鐘": "钟", "鐺": "铛", "鑑": "鉴",
        "長": "长", "門": "门", "閉": "闭", "閒": "闲", "間": "间",
        "閣": "阁", "隊": "队", "陽": "阳", "陰": "阴", "陣": "阵", "階": "阶",
        "隨": "随", "險": "险", "際": "际", "離": "离", "電": "电",
        "靜": "静", "響": "响", "頁": "页", "頂": "顶", "項": "项", "順": "顺",
        "須": "须", "預": "预", "頑": "顽", "頒": "颁", "頓": "顿", "領": "领",
        "頰": "颊", "頻": "频", "題": "题", "額": "额", "顏": "颜",
        "風": "风", "飛": "飞", "飯": "饭", "飲": "饮", "飽": "饱",
        "餓": "饿", "館": "馆", "馬": "马", "駐": "驻", "駛": "驶", "驗": "验",
        "驚": "惊", "鬆": "松", "鬧": "闹", "魚": "鱼", "鮮": "鲜", "鳥": "鸟",
        "鳴": "鸣", "麥": "麦", "黃": "黄", "點": "点", "齊": "齐", "齒": "齿",
        "龍": "龙", "碼": "码", "週": "周", "這": "这", "較": "较", "儘": "尽",
        "編": "编", "輯": "辑", "載": "载", "視": "视", "認": "认", "丟": "丢",
        "擔": "担", "擬": "拟", "網": "网", "採": "采", "並": "并", "試": "试",
        "迴": "回", "沒": "没", "報": "报", "論": "论", "講": "讲", "斬": "斩",
        "釘": "钉", "鐵": "铁", "誠": "诚", "擲": "掷", "執": "执",
    }
)


def timezone_for_profile(profile: str | None = None) -> str:
    """台灣檔保留既有可自訂 TZ；大陸檔固定使用上海時區。"""
    key = profile_name(profile)
    return settings.tz if key == "tw_k12" else "Asia/Shanghai"


def profile_name(profile: str | None = None) -> str:
    return profile or settings.school_profile


def profile_definition(profile: str | None = None) -> dict[str, Any]:
    key = profile_name(profile)
    # Settings validates the environment value; this guard also protects callers that
    # deserialize a persisted value before validation has run.
    return PROFILE_DEFINITIONS.get(key, PROFILE_DEFINITIONS["tw_k12"])


def is_mainland(profile: str | None = None) -> bool:
    return profile_name(profile) == "cn_mainland"


def profile_text(taiwan: str, mainland: str, profile: str | None = None) -> str:
    return mainland if is_mainland(profile) else taiwan


def localize_text(value: str, profile: str | None = None) -> str:
    """Normalize a legacy zh-TW user-facing sentence for the active profile."""
    if not is_mainland(profile):
        return value
    for source, target in MAINLAND_PHRASE_REPLACEMENTS:
        value = value.replace(source, target)
    return value.translate(TRADITIONAL_TO_SIMPLIFIED)


def localize_payload(value: Any, profile: str | None = None) -> Any:
    """Recursively localize message payload values while keeping stable keys intact."""
    if isinstance(value, str):
        return localize_text(value, profile)
    if isinstance(value, list):
        return [localize_payload(item, profile) for item in value]
    if isinstance(value, tuple):
        return tuple(localize_payload(item, profile) for item in value)
    if isinstance(value, dict):
        return {key: localize_payload(item, profile) for key, item in value.items()}
    return value


def display_label(group: str, key: str, profile: str | None = None) -> str:
    """Return a profile-specific label while keeping unknown stored values visible."""
    labels = DISPLAY_LABELS[profile_name(profile)].get(group, {})
    return labels.get(key, key)


def leave_type_label(value: str, profile: str | None = None) -> str:
    return display_label("leave_type", value, profile)


def affected_status_label(value: str, profile: str | None = None) -> str:
    return display_label("affected_status", value, profile)


def substitution_type_label(value: str, profile: str | None = None) -> str:
    return display_label("substitution_type", value, profile)


def export_label(key: str, profile: str | None = None) -> str:
    return display_label("export", key, profile)


def weekday_name(weekday: int, profile: str | None = None) -> str:
    names = WEEKDAY_NAMES[profile_name(profile)]
    return names[weekday - 1] if 1 <= weekday <= len(names) else f"星期{weekday}"


def weekday_names(profile: str | None = None) -> tuple[str, ...]:
    return WEEKDAY_NAMES[profile_name(profile)]


def format_semester_label(academic_year: int, term: int, profile: str | None = None) -> str:
    key = profile_name(profile)
    definition = profile_definition(key)
    if key == "cn_mainland":
        term_label = definition["term_labels"].get(term, f"第{term}学期")
        return definition["academic_year_format"].format(
            year=academic_year, next_year=academic_year + 1, term_label=term_label
        )
    # Preserve the historical Taiwan label exactly, including its spaces.
    return f"{academic_year} 學年度第 {term} 學期"


def validate_academic_year(value: int, profile: str | None = None) -> None:
    definition = profile_definition(profile)
    low = int(definition["academic_year_min"])
    high = int(definition["academic_year_max"])
    if not low <= value <= high:
        raise ValueError(
            profile_text(
                f"學年起始年必須介於 {low} 至 {high}",
                f"学年起始年必须介于 {low} 至 {high}",
                profile,
            )
        )


def public_profile(profile: str | None = None) -> dict[str, Any]:
    key = profile_name(profile)
    definition = profile_definition(key)
    return {
        "profile": key,
        "school_profile": key,
        "locale": definition["locale"],
        "language": definition["language"],
        "timezone": timezone_for_profile(key),
        "tz": timezone_for_profile(key),
        "role_display_names": dict(ROLE_DISPLAY_NAMES[key]),
        "roles": dict(ROLE_DISPLAY_NAMES[key]),
        "terms": dict(TERMS[key]),
        "academic_year": {
            "storage": "start_year",
            "min": definition["academic_year_min"],
            "max": definition["academic_year_max"],
            "label_format": definition["academic_year_format"],
            "term_labels": dict(definition["term_labels"]),
        },
    }
