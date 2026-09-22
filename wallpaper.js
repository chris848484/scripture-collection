/* Scripture wallpaper rendering. Inlined into index.html by the build script. */
window.ScriptureWallpaper = (() => {
  'use strict';
  const WIDTH = 1080;
  const HEIGHT = 1920;
  const FONT = '"Noto Serif KR", "AppleMyungjo", "Batang", "Malgun Gothic", serif';
  let backgroundPromise;
  function loadBackground() {
    if (!backgroundPromise) {
      backgroundPromise = new Promise((resolve, reject) => {
        const source = document.getElementById('wallpaper-background-data')?.textContent.trim();
        if (!source) { reject(new Error('배경 이미지를 찾지 못했습니다.')); return; }
        const background = new Image();
        background.onload = () => resolve(background);
        background.onerror = () => reject(new Error('배경 이미지를 불러오지 못했습니다.'));
        background.src = source;
      }).catch(error => { backgroundPromise = null; throw error; });
    }
    return backgroundPromise;
  }

  function wrapText(context, text, width) {
    const lines = [];
    let line = '';
    for (const word of text.split(/\s+/u)) {
      const candidate = line ? line + ' ' + word : word;
      if (context.measureText(candidate).width <= width) {
        line = candidate;
        continue;
      }
      if (line) lines.push(line);
      line = '';
      for (const character of Array.from(word)) {
        if (line && context.measureText(line + character).width > width) {
          lines.push(line);
          line = character;
        } else line += character;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  function layout(context, passages) {
    const textWidth = 796;
    for (let fontSize = 60; fontSize >= 24; fontSize -= 2) {
      context.font = `${fontSize}px ${FONT}`;
      const paragraphs = passages.map(passage => ({
        number: passage.number,
        lines: wrapText(context, passage.text, textWidth),
      }));
      const lineHeight = Math.round(fontSize * 1.65);
      const paragraphGap = Math.round(fontSize * 0.65);
      const bodyHeight = paragraphs.reduce((sum, p) => sum + p.lines.length * lineHeight, 0)
        + Math.max(0, paragraphs.length - 1) * paragraphGap;
      if (bodyHeight <= 870) return { paragraphs, fontSize, lineHeight, paragraphGap, bodyHeight, textWidth };
    }
    throw new Error('말씀이 너무 길어 한 장에 담을 수 없습니다.');
  }

  async function render(scripture) {
    if (document.fonts?.ready) await document.fonts.ready;
    const background = await loadBackground();
    const canvas = document.createElement('canvas');
    canvas.width = WIDTH;
    canvas.height = HEIGHT;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('이 브라우저에서는 이미지를 만들 수 없습니다.');
    const textLayout = layout(context, scripture.passages);
    const { paragraphs, fontSize, lineHeight, paragraphGap, bodyHeight } = textLayout;
    const scale = Math.max(WIDTH / background.naturalWidth, HEIGHT / background.naturalHeight);
    context.drawImage(background, (WIDTH - background.naturalWidth * scale) / 2, (HEIGHT - background.naturalHeight * scale) / 2, background.naturalWidth * scale, background.naturalHeight * scale);
    const gradient = context.createLinearGradient(0, 0, 0, HEIGHT);
    gradient.addColorStop(0, 'rgba(7,16,32,0.05)');
    gradient.addColorStop(0.2, 'rgba(7,16,32,0.22)');
    gradient.addColorStop(0.73, 'rgba(7,16,32,0.22)');
    gradient.addColorStop(0.85, 'rgba(7,16,32,0.02)');
    gradient.addColorStop(1, 'rgba(7,16,32,0.02)');
    context.fillStyle = gradient;
    context.fillRect(0, 0, WIDTH, HEIGHT);

    // Keep the top clear for a lock-screen clock and the bottom for phone controls.
    const top = 400 + (870 - bodyHeight) / 2;
    const x = 156;
    let y = top;
    context.textBaseline = 'top';
    context.textAlign = 'left';
    for (const paragraph of paragraphs) {
      context.font = `${Math.max(23, Math.round(fontSize * 0.43))}px sans-serif`;
      context.fillStyle = '#b4c5df';
      context.fillText(String(paragraph.number), 99, y + fontSize * 0.19);
      context.font = `${fontSize}px ${FONT}`;
      context.fillStyle = '#f8f6f0';
      for (const line of paragraph.lines) {
        context.fillText(line, x, y);
        y += lineHeight;
      }
      y += paragraphGap;
    }
    const referenceY = top + bodyHeight + 72;
    context.fillStyle = '#91a7c6';
    context.fillRect(x, referenceY, 56, 2);
    context.font = '40px "Malgun Gothic", sans-serif';
    context.fillStyle = '#d3deed';
    context.fillText(scripture.reference, x, referenceY + 33);

    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob(value => value ? resolve(value) : reject(new Error('이미지를 저장하지 못했습니다.')), 'image/png');
    });
    return { blob, width: WIDTH, height: HEIGHT, layout: textLayout };
  }

  return { render };
})();
