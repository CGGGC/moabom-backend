"""Render a verified schema snapshot as a standalone SVG using only stdlib."""

import argparse
import json
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
POSITIONS = {
    "user_activity_events": (72, 136, 398),
    "user_category_preferences": (72, 432, 398),
    "users": (72, 804, 398),
    "opportunities": (650, 136, 450),
}
HEADER = 46
ROW = 32


def render(snapshot: dict) -> str:
    positions = snapshot.get("positions", POSITIONS)
    canvas_width, canvas_height = snapshot.get("canvas", [1172, 1240])
    title = escape(snapshot.get("title", "모아봄 데이터베이스 구조"))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-labelledby="title description">',
        f'<title id="title">{title}</title>',
        '<desc id="description">실제 Supabase 자료형과 제약. 실선은 DB 외래키, 점선은 DB 외래키가 없는 코드상의 식별 관계입니다.</desc>',
        '<defs><pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#e6eaf0"/></pattern></defs>',
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif} .column{font-family:"SFMono-Regular",Menlo,Consolas,monospace;font-size:15px;fill:#283445} .type{font-family:"SFMono-Regular",Menlo,Consolas,monospace;font-size:13px;fill:#7b8794}</style>',
        f'<rect width="{canvas_width}" height="{canvas_height}" fill="#fbfcfe"/>',
        f'<rect y="110" width="{canvas_width}" height="{canvas_height - 220}" fill="url(#dots)"/>',
        f'<text x="72" y="50" font-size="26" font-weight="700" fill="#18283d">{title}</text>',
        f'<text x="72" y="82" font-size="14" fill="#68778b">Supabase 읽기 전용 실측 · 테이블 {len(snapshot["tables"])}개 · 2026-10-08</text>',
    ]

    def anchor(table, column, side):
        x, y, width = positions[table]
        index = next(i for i, row in enumerate(snapshot["tables"][table]) if row[0] == column)
        return (x if side == "left" else x + width, y + HEADER + ROW * index + ROW / 2)

    for relation in snapshot["foreign_keys_visible"]:
        start = anchor(*relation["from"], "right")
        end = anchor(*relation["to"], "left")
        parts.append(f'<path d="M{start[0]} {start[1]} H580 V{end[1]} H{end[0]}" fill="none" stroke="#3475c9" stroke-width="2.2"/>')
        parts.append('<text x="501" y="153" font-size="12" fill="#3475c9">공고 외래키</text>')

    for index, relation in enumerate(snapshot["logical_links_from_code"]):
        side = "left" if index == 0 else "right"
        start = anchor(*relation["from"], side)
        end = anchor(*relation["to"], side)
        rail = 38 if index == 0 else 536
        parts.append(f'<path d="M{start[0]} {start[1]} H{rail} V{end[1]} H{end[0]}" fill="none" stroke="#a8b5c5" stroke-width="1.7" stroke-dasharray="6 5"/>')

    for name, columns in snapshot["tables"].items():
        x, y, width = positions[name]
        height = HEADER + ROW * len(columns)
        parts.append(f'<rect x="{x}" y="{y + 3}" width="{width}" height="{height}" rx="9" fill="#dfe5ee" opacity="0.4"/>')
        parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="9" fill="white" stroke="#d9e0e9"/>')
        parts.append(f'<rect x="{x + 16}" y="{y + 17}" width="13" height="13" rx="2" fill="none" stroke="#748498"/>')
        parts.append(f'<path d="M{x + 16} {y + 21} H{x + 29} M{x + 20} {y + 17} V{y + 30}" stroke="#748498"/>')
        parts.append(f'<text x="{x + 40}" y="{y + 30}" font-size="17" font-weight="600" fill="#1d2b3d">{escape(name)}</text>')
        for index, (column, datatype, nullable, key) in enumerate(columns):
            top = y + HEADER + ROW * index
            center = top + ROW / 2
            parts.append(f'<line x1="{x}" y1="{top}" x2="{x + width}" y2="{top}" stroke="#edf0f4"/>')
            fill = "white" if nullable else "#596778"
            parts.append(f'<path d="M{x + 49} {center - 4} L{x + 53} {center} L{x + 49} {center + 4} L{x + 45} {center} Z" fill="{fill}" stroke="#596778"/>')
            if key:
                color = "#245ea8" if key == "PK" else "#7b5a9d"
                parts.append(f'<text x="{x + 12}" y="{center + 4}" font-size="10" font-weight="700" fill="{color}">{key}</text>')
            parts.append(f'<text class="column" x="{x + 65}" y="{center + 5}">{escape(column)}</text>')
            parts.append(f'<text class="type" x="{x + width - 16}" y="{center + 4}" text-anchor="end">{escape(datatype)}</text>')

    footer_y = canvas_height - 140
    parts.extend([
        f'<line x1="72" y1="{footer_y}" x2="111" y2="{footer_y}" stroke="#3475c9" stroke-width="2.2"/>',
        f'<text x="122" y="{footer_y + 5}" font-size="13" fill="#55667b">실제 DB 외래키</text>',
        f'<line x1="390" y1="{footer_y}" x2="429" y2="{footer_y}" stroke="#a8b5c5" stroke-width="1.7" stroke-dasharray="6 5"/>',
        f'<text x="440" y="{footer_y + 5}" font-size="13" fill="#55667b">코드상의 식별 관계 · DB 외래키 없음</text>',
        f'<text x="72" y="{footer_y + 40}" font-size="13" fill="#55667b">PK 기본키   UQ 고유 제약   ◆ 필수 값   ◇ NULL 허용</text>',
    ])
    notes = snapshot.get("notes", [
        "user_category_preferences: (user_id, category) 복합 기본키",
        "추천 조회: 사용자별 카테고리 점수와 opportunities.category를 JOIN",
    ])
    for index, note in enumerate(notes):
        parts.append(f'<text x="72" y="{canvas_height - 69 + 26 * index}" font-size="13" fill="#68778b">{escape(note)}</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "docs/schema-snapshot.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/images/database-schema.svg")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(json.loads(args.input.read_text())), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
