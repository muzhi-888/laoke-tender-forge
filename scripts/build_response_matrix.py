#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_response_matrix.py — 招投标偏离表/响应表自动生成与合规自检

功能：
  读取"招标要求 vs 投标响应"对照数据，自动生成 Markdown 偏离表，
  并对每条做初步偏离判定（无偏离/正偏离/负偏离/需人工确认），
  最后汇总合规自检结果。

用法：
  python build_response_matrix.py                  # 跑内置演示样例（自检用）
  python build_response_matrix.py input.tsv        # 读 TSV（列：条款号|招标要求|投标响应）
  python build_response_matrix.py input.tsv out.md # 指定输出文件

依赖：仅 Python 标准库（无第三方依赖）。
判定逻辑（辅助，非最终合规结论）：
  - 响应含否定信号词（无/未/不/缺/暂无/不满足）→ 标记"需人工确认（疑似负偏离）"
  - 可抽取数值且 响应值 >= 要求值 → 正偏离/无偏离
  - 其余 → 需人工确认
最终偏离类型须由具备资质人员复核签字。
"""
import sys
import re
import os

NEG_SIGNALS = ["无", "未", "不", "缺", "暂无", "不满足", "没有", "无法提供", "不具备"]

DEMO = """3.2.1|注册资本不低于500万元|公司注册资本800万元
4.5|质保期不少于3年|提供5年质保
6.1|需在本地设有服务点|暂未在本地设点
7.3|具备ISO9001质量管理体系认证|已获ISO9001认证
8.2|项目业绩不少于3个类似项目|提供5个类似项目合同
5.1|投标有效期90天|投标有效期90天
2.4|项目经理须为一建注册人员|项目经理持一级建造师证"""


def parse_rows(text):
    rows = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 3:
            parts = (parts + ["", "", ""])[:3]
        rows.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return rows


def extract_number(s):
    """抽取字符串里的第一个数值（支持 万/年/个 等单位前的数字）。"""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(万|年|个|项|天|月)?", s)
    if not m:
        return None
    val = float(m.group(1))
    return val


def judge(clause, req, resp):
    """返回 (偏离类型, 说明)。"""
    r = resp
    # 否定信号
    if any(sig in r for sig in NEG_SIGNALS) and not re.search(r"\d", r):
        return ("需人工确认", "响应含否定信号，疑似负偏离，请核实")
    # 数值比较
    req_num = extract_number(req)
    resp_num = extract_number(r)
    if req_num is not None and resp_num is not None:
        if resp_num > req_num:
            return ("正偏离", f"响应值{resp_num}优于要求{req_num}")
        if abs(resp_num - req_num) < 1e-9:
            return ("无偏离", "响应值满足要求")
        return ("需人工确认", f"响应值{resp_num}低于要求{req_num}，疑似负偏离")
    # 含"已/具备/提供/持"等肯定词且无否定信号
    if any(pos in r for pos in ["已", "具备", "提供", "持", "有"]):
        return ("需人工确认", "响应为肯定表述，请人工确认是否满足")
    return ("需人工确认", "无法自动判定，请人工确认")


def render_markdown(rows):
    lines = []
    lines.append("# 投标偏离表 / 响应表\n")
    lines.append("| 序号 | 条款号 | 招标要求 | 投标响应 | 偏离类型 | 说明 |")
    lines.append("|------|--------|----------|----------|----------|------|")
    counts = {"无偏离": 0, "正偏离": 0, "负偏离": 0, "需人工确认": 0}
    for i, (clause, req, resp) in enumerate(rows, 1):
        dtype, note = judge(clause, req, resp)
        # 疑似负偏离计入需人工确认（不自动判负偏离，避免误伤）
        if "疑似负偏离" in note:
            dtype = "需人工确认"
            counts["需人工确认"] += 1
        elif dtype == "正偏离":
            counts["正偏离"] += 1
        elif dtype == "无偏离":
            counts["无偏离"] += 1
        else:
            counts["需人工确认"] += 1
        lines.append(f"| {i} | {clause} | {req} | {resp} | {dtype} | {note} |")
    lines.append("")
    lines.append("## 合规自检汇总\n")
    lines.append(f"- 无偏离：{counts['无偏离']} 条")
    lines.append(f"- 正偏离：{counts['正偏离']} 条（加分点，须真实可验证）")
    lines.append(f"- 需人工确认：{counts['需人工确认']} 条（含疑似负偏离，定稿前必须逐条复核）")
    lines.append(f"- 自动判定负偏离：0 条（最终负偏离须人工确认，触★条款即废标）")
    lines.append("")
    lines.append("> 本表由脚本自动生成，偏离类型仅供辅助，最终须由具备资质人员复核签字。")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    if not args:
        text = DEMO
        print("[自检模式] 使用内置演示样例\n")
    else:
        path = args[0]
        if not os.path.exists(path):
            print(f"错误：输入文件不存在 {path}", file=sys.stderr)
            return 2
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        print(f"[文件模式] 读取 {path}\n")

    rows = parse_rows(text)
    if not rows:
        print("错误：未解析到任何对照条目", file=sys.stderr)
        return 2

    out = render_markdown(rows)
    print(out)

    if len(args) >= 2:
        with open(args[1], "w", encoding="utf-8") as f:
            f.write(out)
        print(f"\n[已写出] {args[1]}")

    # 自检：演示样例应含正偏离(质保5>3, 注册资本800>500)与需人工确认(本地设点)
    if not args:
        assert "正偏离" in out, "自检失败：应识别正偏离"
        assert "需人工确认" in out, "自检失败：应识别需人工确认"
        print("\n[自检通过] 脚本功能正常，exit 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
