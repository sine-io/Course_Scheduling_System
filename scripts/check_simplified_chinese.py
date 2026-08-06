#!/usr/bin/env python3
"""检查受版本控制文本中的旧本地化标识、旧术语和常见非简体字形。"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def joined(*parts: str) -> str:
    """拼接受检词，避免检查脚本自身包含完整禁用词。"""

    return "".join(parts)


@dataclass(frozen=True)
class LiteralRule:
    name: str
    value: str


@dataclass(frozen=True)
class RegexRule:
    name: str
    pattern: re.Pattern[str]


LITERAL_RULES = (
    LiteralRule("旧上游仓库标识", joined("begin", "0808")),
    LiteralRule("已删除的部署模板标识", joined("tw", "_k12")),
    LiteralRule("已删除的部署模板标识", joined("cn", "_mainland")),
    LiteralRule("已删除的语言标识", joined("zh", "-TW")),
    LiteralRule("已删除的语言标识", joined("zh", "-Hant")),
    LiteralRule("已删除的时区", joined("Asia", "/Taipei")),
    LiteralRule("已删除的环境变量", joined("SCHOOL", "_PROFILE")),
    LiteralRule("已删除的错误码", joined("school", "_profile_locked")),
    LiteralRule("已删除的服务模块", joined("deployment", "_profile")),
    LiteralRule("已删除的本地化函数", joined("profile", "_text")),
    LiteralRule("已删除的本地化函数", joined("localize", "_payload")),
    LiteralRule("已删除的本地化函数", joined("localize", "_text")),
    LiteralRule("已删除的语言分支", joined("is", "Mainland")),
    LiteralRule("已删除的语言分支", joined("is", "_mainland")),
    LiteralRule("已删除的前端组合函数", joined("use", "ProfileText")),
    LiteralRule("不再使用的通知平台名称", joined("LI", "NE")),
    LiteralRule("不再使用的地区名称", joined("台", "湾")),
    LiteralRule("不再使用的字形说明", joined("繁", "体")),
    LiteralRule("不再支持的纪年", joined("民", "国")),
    LiteralRule("旧学年用语", joined("学年", "度")),
    LiteralRule("旧学校类型", joined("技", "高")),
    LiteralRule("旧学校类型", joined("普通型", "高中")),
    LiteralRule("旧学校类型", joined("综合型", "高中")),
    LiteralRule("旧学校类型", joined("技术型", "高中")),
    LiteralRule("旧角色名称", joined("教务", "员")),
    LiteralRule("旧角色名称", joined("组", "长")),
    LiteralRule("旧教务术语", joined("配", "课")),
    LiteralRule("旧教务术语", joined("节次", "表")),
    LiteralRule("旧教务术语", joined("基础", "资", "料")),
    LiteralRule("旧教务术语", joined("资", "料", "库")),
    LiteralRule("旧教务术语", joined("资", "料")),
    LiteralRule("旧教务术语", joined("钟", "点")),
    LiteralRule("旧教务术语", joined("假", "别")),
    LiteralRule("旧教务术语", joined("处", "置")),
    LiteralRule("旧教务术语", joined("原任", "教师")),
    LiteralRule("旧教务术语", joined("待", "就绪")),
    LiteralRule("旧教务术语", joined("已", "就绪")),
    LiteralRule("旧教务术语", joined("跑", "班")),
    LiteralRule("旧教务术语", joined("封", "存")),
    LiteralRule("旧教务术语", joined("调代", "课")),
    LiteralRule("旧教务术语", joined("导", "师")),
    LiteralRule("旧教务术语", joined("课", "务")),
    LiteralRule("旧教务术语", joined("校历", "例外")),
    LiteralRule("旧软件用语", joined("检", "视")),
    LiteralRule("旧软件用语", joined("核", "可")),
    LiteralRule("旧软件用语", joined("身", "分")),
    LiteralRule("旧软件用语", joined("回", "传")),
    LiteralRule("旧软件用语", joined("透", "过")),
    LiteralRule("旧软件用语", joined("预", "设")),
    LiteralRule("旧软件用语", joined("资", "讯")),
    LiteralRule("旧软件用语", joined("网", "路")),
    LiteralRule("旧软件用语", joined("程", "式")),
    LiteralRule("旧软件用语", joined("专", "案")),
    LiteralRule("旧软件用语", joined("伺服", "器")),
    LiteralRule("旧软件用语", joined("伫", "列")),
    LiteralRule("旧软件用语", joined("登", "入")),
    LiteralRule("旧软件用语", joined("设", "定")),
    LiteralRule("旧软件用语", joined("位", "址")),
    LiteralRule("旧软件用语", joined("变", "数")),
    LiteralRule("旧软件用语", joined("快", "取")),
    LiteralRule("旧软件用语", joined("执行", "绪")),
    LiteralRule("旧软件用语", joined("讯", "息")),
    LiteralRule("旧软件用语", joined("品", "质")),
    LiteralRule("旧软件用语", joined("取", "得")),
    LiteralRule("旧软件用语", joined("储", "存")),
    LiteralRule("旧软件用语", joined("栏", "位")),
    LiteralRule("旧软件用语", joined("清", "单")),
    LiteralRule("旧软件用语", joined("列", "印")),
    LiteralRule("旧软件用语", joined("建", "置")),
    LiteralRule("旧软件用语", joined("布", "署")),
    LiteralRule("旧软件用语", joined("相", "依")),
    LiteralRule("旧软件用语", joined("套", "件")),
    LiteralRule("旧软件用语", joined("内", "建")),
    LiteralRule("旧软件用语", joined("客", "制")),
    LiteralRule("旧软件用语", joined("支", "援")),
    LiteralRule("旧软件用语", joined("唯", "读")),
    LiteralRule("旧软件用语", joined("视", "窗")),
    LiteralRule("旧软件用语", joined("串", "接")),
    LiteralRule("旧软件用语", joined("揭", "露")),
    LiteralRule("旧软件用语", joined("备", "援")),
    LiteralRule("旧软件用语", joined("寄", "信")),
    LiteralRule("旧软件用语", joined("略", "过")),
    LiteralRule("旧软件用语", joined("批", "次")),
    LiteralRule("旧软件用语", joined("回", "应")),
    LiteralRule("旧软件用语", joined("效", "能")),
    LiteralRule("旧软件用语", joined("范", "例")),
    LiteralRule("旧软件用语", joined("连", "线")),
    LiteralRule("旧软件用语", joined("搜", "寻")),
    LiteralRule("旧软件用语", joined("贴", "上")),
    LiteralRule("旧软件用语", joined("游", "标")),
    LiteralRule("旧软件用语", joined("区", "网")),
    LiteralRule("旧软件用语", joined("行动", "网络")),
    LiteralRule("旧软件用语", joined("异", "动")),
    LiteralRule("旧软件用语", joined("模", "组")),
    LiteralRule("旧软件用语", joined("情", "境")),
    LiteralRule("旧软件用语", "\u57e0"),
    LiteralRule("旧软件用语", joined("凭", "证")),
    LiteralRule("旧软件用语", joined("载", "入")),
    LiteralRule("旧软件用语", joined("拖", "曳")),
    LiteralRule("旧软件用语", joined("侦", "测")),
    LiteralRule("旧软件用语", joined("辨", "识")),
    LiteralRule("旧软件用语", joined("旗", "标")),
    LiteralRule("旧软件用语", joined("产", "生")),
    LiteralRule("旧软件用语", joined("进", "阶")),
    LiteralRule("旧软件用语", joined("维", "持")),
    LiteralRule("旧软件用语", joined("字", "元")),
    LiteralRule("旧软件用语", joined("字", "型")),
    LiteralRule("旧软件用语", joined("杂", "凑")),
    LiteralRule("旧软件用语", joined("签", "章")),
    LiteralRule("旧软件用语", joined("交", "易式")),
    LiteralRule("旧软件用语", joined("管", "线")),
    LiteralRule("旧软件用语", joined("核取", "方块")),
    LiteralRule("旧软件用语", joined("现", "况")),
    LiteralRule("旧软件用语", joined("跟", "著")),
    LiteralRule("旧软件用语", joined("照", "著")),
    LiteralRule("旧软件用语", joined("接", "著")),
    LiteralRule("旧软件用语", joined("写", "著")),
    LiteralRule("旧软件用语", joined("留", "著")),
    LiteralRule("旧软件用语", joined("对", "著")),
    LiteralRule("旧软件用语", joined("随", "著")),
    LiteralRule("旧软件用语", joined("试", "著")),
    LiteralRule("旧软件用语", joined("非", "同步")),
    LiteralRule("旧软件用语", joined("纯", "量")),
    LiteralRule("旧软件用语", joined("宣", "告")),
    LiteralRule("旧软件用语", joined("平行", "启动")),
    LiteralRule("旧软件用语", joined("选", "单")),
    LiteralRule("旧软件用语", joined("点", "选")),
    LiteralRule("旧软件用语", joined("建", "构")),
    LiteralRule("旧软件用语", joined("串", "流")),
    LiteralRule("旧软件用语", joined("送", "出")),
    LiteralRule("旧软件用语", joined("寄件", "匣")),
    LiteralRule("旧软件用语", joined("信", "箱")),
    LiteralRule("旧软件用语", joined("介", "于")),
    LiteralRule("旧软件用语", joined("资", "安")),
    LiteralRule("旧项目用语", joined("全", "案")),
    LiteralRule("旧项目用语", joined("各", "档")),
    LiteralRule("旧业务用语", joined("实", "务")),
    LiteralRule("旧教务术语", joined("进", "修")),
    LiteralRule("旧软件用语", joined("即时", "进度")),
    LiteralRule("旧软件用语", joined("即时", "统计")),
    LiteralRule("旧软件用语", joined("即时", "冲突")),
    LiteralRule("旧软件用语", joined("即时", "同步")),
    LiteralRule("旧软件用语", joined("即时", "生效")),
    LiteralRule("口语化旧用语", joined("挡", "下")),
    LiteralRule("口语化旧用语", joined("挡", "住")),
    LiteralRule("口语化旧用语", joined("被", "挡")),
    LiteralRule("口语化旧用语", joined("挡", "死")),
    LiteralRule("口语化旧用语", joined("不", "挡")),
    LiteralRule("口语化旧用语", "\u635e"),
    LiteralRule("口语化旧用语", joined("照", "跑")),
    LiteralRule("口语化旧用语", joined("灌", "水")),
    LiteralRule("口语化旧用语", joined("炸", "锅")),
    LiteralRule("口语化旧用语", joined("误", "伤")),
    LiteralRule("口语化旧用语", joined("喷", "出")),
    LiteralRule("口语化旧用语", joined("吞", "掉")),
    LiteralRule("口语化旧用语", joined("吞", "信息")),
    LiteralRule("口语化旧用语", joined("只", "印")),
    LiteralRule("旧软件用语", "\u63b7"),
    LiteralRule("旧数据量词", joined("一", "笔")),
    LiteralRule("旧数据量词", joined("每", "笔")),
    LiteralRule("旧数据量词", joined("各", "笔")),
    LiteralRule("旧数据量词", joined("该", "笔")),
    LiteralRule("旧数据量词", joined("这", "笔")),
    LiteralRule("旧数据量词", joined("那", "笔")),
    LiteralRule("旧数据量词", joined("整", "笔")),
    LiteralRule("旧数据量词", joined("笔", "数")),
    LiteralRule("旧教务术语", joined("主", "教")),
    LiteralRule("旧学校用语", joined("业界", "师资")),
    LiteralRule("旧学校用语", joined("工", "场")),
    LiteralRule("旧学校用语", joined("群", "科")),
    LiteralRule("旧学校用语", joined("部", "定")),
    LiteralRule("旧学校用语", joined("认", "养")),
    LiteralRule("旧软件用语", joined("复", "原")),
    LiteralRule("旧课程名称", joined("国", "文")),
    LiteralRule("旧课程名称", joined("国", "语")),
    LiteralRule("旧课程名称", joined("健康与", "体育")),
    LiteralRule("旧课程名称", joined("综合", "活动")),
    LiteralRule("旧课程名称", joined("弹性", "学习")),
    LiteralRule("旧课程名称", joined("多元", "选修")),
    LiteralRule("旧课程名称", joined("生活", "科技")),
    LiteralRule("旧课程名称", joined("公民与", "社会")),
    LiteralRule("旧地区域名", joined(".edu", ".tw")),
)

REGEX_RULES = (
    RegexRule("旧小学类型", re.compile(r"(?<!全)" + joined("国", "小"))),
    RegexRule("旧初中类型", re.compile(r"(?<!全)" + joined("国", "中"))),
    RegexRule(
        "笼统教务术语",
        re.compile(r"(?<!实训)(?<!户外)(?<!教室/)" + joined("场", "地")),
    ),
    RegexRule("双文案调用", re.compile(r"\btr\s*\(")),
    RegexRule("旧数据量词", re.compile(r"(?:\d+|N)\s*" + joined("笔"))),
    RegexRule(
        "Docker 命令缺少 sudo",
        re.compile(r"(?<!sudo )\bdocker\s+(?:compose|build|run|exec|logs|ps|stats|--version)\b"),
    ),
    RegexRule(
        "旧学年标签格式",
        re.compile(r"(?<![-\d])(?:19|20)\d{2}\s*学年(?:度)?第\s*[一二12]\s*学期"),
    ),
)

# 常见非简体字形。用 Unicode 转义保存，避免规则文件自身触发检查。
TRADITIONAL_GLYPHS = set(
    "\u81fa\u7063\u9ad4\u5b78\u570b\u8ab2\u5e2b\u9580\u9593\u6642\u9418\u9ede"
    "\u8655\u6a94\u8cc7\u8a0a\u7db2\u8a2d\u5e33\u865f\u555f\u52d5\u95dc\u9589"
    "\u532f\u5132\u522a\u7de8\u8f2f\u9810\u6aa2\u8996\u7e3d\u89bd\u72c0\u614b"
    "\u8a18\u9304\u8acb\u985e\u5225\u5c0e\u54e1\u7d44\u9577\u8207\u500b\u7b46"
    "\u5f35\u689d\u6a5f\u52d9\u5099\u5fa9\u9084\u767c\u4f48\u90f5\u50b3\u78ba"
    "\u8a8d\u8b80\u5beb\u986f\u6578\u64da\u5eab\u8f09\u904b\u9023\u7dda\u9078"
    "\u64c7\u958b\u7d50\u932f\u8aa4\u61c9\u8a72\u8b93\u9019\u88e1\u7121\u70ba"
    "\u5f9e\u5c0d\u5c07\u6703\u8f49\u63db\u4f47\u57f7\u66ab\u9a57\u8b49\u6e2c"
    "\u69cb\u5be6\u74b0\u9801\u6b04\u9215\u8f38\u6a19\u7c64\u984c\u6b0a\u50c5"
    "\u5247\u55ae\u96d9\u9031\u7bc0\u6b77\u66c6\u8fb2\u78bc\u806f\u7d61\u96fb"
    "\u8a71\u5ee3\u820a\u7dad\u8b77\u7570\u593e\u88fd\u5716\u756b\u8072\u9234"
    "\u8853\u8a9e\u7d9c\u5f48\u7fd2\u7a31\u8b02\u5340\u4f75\u6eff\u8cfc\u8ce3"
    "\u96e3\u9ede\u8f03\u7d93\u6fdf\u5f8c\u99ac"
)


def tracked_text_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    files: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = ROOT / raw.decode("utf-8", errors="surrogateescape")
        if path.is_file():
            files.append(path)
    return files


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        print(f"无法读取 {path.relative_to(ROOT)}：{exc}", file=sys.stderr)
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def check_line(
    relative: Path,
    line_number: int,
    line: str,
    *,
    skip_windows_docker: bool = False,
) -> list[str]:
    findings: list[str] = []
    for rule in LITERAL_RULES:
        start = 0
        while (column := line.find(rule.value, start)) >= 0:
            findings.append(
                f"{relative}:{line_number}:{column + 1}: {rule.name}：{rule.value!r}"
            )
            start = column + max(1, len(rule.value))
    for rule in REGEX_RULES:
        # Windows Docker Desktop 没有 sudo；PowerShell 安装脚本使用原生 docker
        # 命令，仍然会检查其余简体中文和术语规则。
        if skip_windows_docker and rule.name == "Docker 命令缺少 sudo":
            continue
        for match in rule.pattern.finditer(line):
            findings.append(
                f"{relative}:{line_number}:{match.start() + 1}: "
                f"{rule.name}：{match.group(0)!r}"
            )
    for column, char in enumerate(line, 1):
        if char in TRADITIONAL_GLYPHS:
            findings.append(
                f"{relative}:{line_number}:{column}: 非简体字形：{char!r}"
            )
    return findings


def main() -> int:
    findings: list[str] = []
    for path in tracked_text_files():
        text = read_text(path)
        if text is None:
            continue
        relative = path.relative_to(ROOT)
        skip_windows_docker = relative.suffix.lower() == ".ps1"
        for line_number, line in enumerate(text.splitlines(), 1):
            findings.extend(
                check_line(
                    relative,
                    line_number,
                    line,
                    skip_windows_docker=skip_windows_docker,
                )
            )

    if findings:
        print("仓库中文规范检查失败：", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        print(f"共发现 {len(findings)} 处问题。", file=sys.stderr)
        return 1

    print("仓库中文规范检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
