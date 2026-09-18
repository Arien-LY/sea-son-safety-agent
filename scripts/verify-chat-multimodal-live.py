"""Explicit, bounded live acceptance using generated non-personal images only."""
import argparse
import io
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx
from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-external', action='store_true', help='Authorize up to three paid synthetic chat turns')
    args = parser.parse_args()
    if not args.allow_external:
        parser.error('Live calls require --allow-external; normal tests remain offline.')
    results = []
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=195) as client:
        runtime = client.get('/api/text/runtime').json()
        if runtime.get('mode') != 'real' or not runtime.get('image_configured'):
            raise RuntimeError('Configured real image service is required')
        images = []
        for index in range(2):
            image = Image.new('RGB', (640, 480), 'white')
            draw = ImageDraw.Draw(image)
            if index == 0:
                draw.rectangle((50, 60, 240, 250), fill='red')
                draw.ellipse((350, 60, 540, 250), fill='blue')
                draw.text((170, 340), '17 * 23 = ?', fill='black', font=ImageFont.load_default(size=42))
            else:
                draw.polygon([(320, 50), (100, 360), (540, 360)], fill='green')
            raw = io.BytesIO()
            image.save(raw, format='PNG')
            uploaded = client.post('/api/photos', content=raw.getvalue(),
                headers={'Content-Type':'image/png', 'X-Upload-Authorized':'true'})
            uploaded.raise_for_status()
            images.append(uploaded.json()['photo_id'])
        session = None
        cases = [
            ('image_text_tools', '你能看到这张图吗？请描述图形的颜色和相对位置，读出图片中的算式，然后调用 calculate 计算它。不需要工单。', images[0], True),
            ('image_only', '', images[1], False),
            ('text_follow_up', '这是纯文字连通性测试，请只回答 PURE_TEXT_OK，不需要工具或工单。', None, False),
        ]
        for index, (name, message, photo_id, tools) in enumerate(cases):
            body = dict(request_id='live-multimodal-'+uuid4().hex, intent='auto', input={'message':message},
                        model=runtime['model'], allow_external=True, tools_enabled=tools)
            if photo_id:
                body.update(photo_id=photo_id, allow_image_external=True)
            if name == 'text_follow_up':
                body.update(consultation_id=session['consultation_id'], expected_turn=session['turn'])
            start = time.monotonic()
            response = client.post('/api/text-consultations', json=body)
            response.raise_for_status()
            session = response.json()
            row = dict(case=name, seconds=round(time.monotonic()-start, 2), model=session['model'],
                       answer=session['reply']['answer'], tools=session['tool_results'], photo_id=session.get('photo_id'))
            results.append(row)
            print(json.dumps(row, ensure_ascii=True), flush=True)
    output = Path('data/chat-multimodal-live.json')
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
