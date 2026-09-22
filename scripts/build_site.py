"""Build a self-contained HTML reader from faithfully extracted PDF content."""
import json
import base64
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    data = json.loads((ROOT / 'content.json').read_text(encoding='utf-8'))
    categories = data['categories']
    toc = []
    sections = []
    verse_count = 0
    for index, category in enumerate(categories, 1):
        section_id = f'topic-{index:02d}'
        title = escape(category['title'])
        toc.append(f'<li><a href="#{section_id}"><span class="toc-number">{index:02d}</span><span>{title}</span></a></li>')
        parts = [f'<section class="topic" id="{section_id}" aria-labelledby="{section_id}-title">',
                 f'<header class="topic-header"><span class="chapter-number">{index:02d} / {len(categories):02d}</span><h2 id="{section_id}-title">{title}</h2></header>']
        last_subcategory = None
        for verse_index, verse in enumerate(category['verses'], 1):
            verse_count += 1
            subcategory = verse.get('subcategory')
            if subcategory and subcategory != last_subcategory:
                parts.append(f'<p class="subcategory">{escape(subcategory)}</p>')
                last_subcategory = subcategory
            verse_id = f'{section_id}-verse-{verse_index:02d}'
            ref = escape(verse['reference'])
            parts.append(f'<article class="verse" id="{verse_id}" data-wallpaper="wallpapers/verse-{verse_count:02d}.png" aria-labelledby="{verse_id}-title"><div class="verse-heading"><h3 id="{verse_id}-title">{ref}</h3><div class="verse-tools"><button class="copy-verse" type="button" aria-label="{ref} 말씀 전체 복사 및 선택" aria-pressed="false" hidden>복사</button><a class="verse-link" href="#{verse_id}" aria-label="{ref} 바로가기">#</a></div></div>')
            for passage in verse['passages']:
                number = escape(str(passage['number']))
                text = escape(passage['text'])
                parts.append(f'<p class="passage"><span class="verse-number" aria-label="{number}절">{number}</span>{text}</p>')
            parts.append('</article>')
        parts.append('<div class="topic-bottom"><a href="#top">목차로 ↑</a></div></section>')
        sections.append('\n'.join(parts))
    template = (ROOT / 'site.template.html').read_text(encoding='utf-8')
    result = template.replace('@@TOC@@', '\n'.join(toc)).replace('@@CONTENT@@', '\n'.join(sections))
    result = result.replace('@@WALLPAPER_SCRIPT@@', (ROOT / 'wallpaper.js').read_text(encoding='utf-8'))
    background = base64.b64encode((ROOT / 'wallpaper-background.png').read_bytes()).decode('ascii')
    result = result.replace('@@WALLPAPER_BACKGROUND@@', 'data:image/png;base64,' + background)
    result = result.replace('@@TOPIC_COUNT@@', str(len(categories))).replace('@@VERSE_COUNT@@', str(verse_count))
    assert '@@' not in result, 'Unresolved template placeholder'
    (ROOT / 'index.html').write_text(result, encoding='utf-8')
    print(f'Built index.html: {len(categories)} topics, {verse_count} scripture passages, {len(result.encode("utf-8")):,} bytes')


if __name__ == '__main__':
    build()
