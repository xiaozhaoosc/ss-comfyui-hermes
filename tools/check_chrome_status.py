import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        flow_page = None
        for page in b.contexts[0].pages:
            if 'flow.google.com' in page.url:
                flow_page = page
                break
        
        if not flow_page:
            print("Flow page not found!")
            await b.close()
            return
            
        print(f"Flow Page URL: {flow_page.url}")
        # 截图保存当前 Flow 状态
        await flow_page.screenshot(path="output/2026-10-10/route_a/debug/flow_current_canvas.png")
        print("Saved output/2026-10-10/route_a/debug/flow_current_canvas.png")

        # 检查页面上的通知/Toast/失败卡片/历史记录
        info = await flow_page.evaluate("""() => {
            let toasts = Array.from(document.querySelectorAll('.mat-mdc-snack-bar-label, [role="alert"], .error, [class*="error"], [class*="failed"]')).map(el => el.innerText.trim());
            
            // 查找所有卡片中的状态文字或错误提示
            let cards = Array.from(document.querySelectorAll('[class*="card"], [class*="item"], [class*="media"]')).map(c => {
                let text = c.innerText ? c.innerText.trim() : '';
                return text;
            }).filter(t => t.toLowerCase().includes('fail') || t.toLowerCase().includes('error') || t.toLowerCase().includes('policy') || t.toLowerCase().includes('refund'));

            // 查找历史记录侧边栏或按钮
            let historyBtn = Array.from(document.querySelectorAll('button')).find(b => (b.innerText || '').includes('history') || (b.getAttribute('aria-label') || '').includes('history'));
            
            return {
                toasts: toasts,
                failed_cards: cards.slice(0, 5),
                has_history_btn: !!historyBtn,
                history_btn_text: historyBtn ? (historyBtn.innerText || historyBtn.getAttribute('aria-label')) : null
            };
        }""")
        print("Inspection info:", info)
        await b.close()

if __name__ == '__main__':
    asyncio.run(main())
