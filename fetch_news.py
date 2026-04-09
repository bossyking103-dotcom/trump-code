import json
import requests
import os

API_URL = "http://localhost:8890/api/signals"
RECENT_URL = "http://localhost:8890/api/recent-posts"
LAST_SEEN_FILE = os.path.join(os.path.dirname(__file__), "last_seen.json")

def load_seen():
    if os.path.exists(LAST_SEEN_FILE):
        try:
            with open(LAST_SEEN_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_seen(data):
    with open(LAST_SEEN_FILE, 'w') as f:
        json.dump(data, f)

def main():
    try:
        # 取得系統今日狀態
        res = requests.get(API_URL, timeout=5)
        if res.status_code != 200:
            print("NO_NEW_ARTICLES")
            return
            
        data = res.json()
        consensus = data.get("consensus", "NEUTRAL")
        signals = data.get("signals", [])
        
        # 取得最新文章
        res_posts = requests.get(RECENT_URL, timeout=5)
        posts_data = res_posts.json() if res_posts.status_code == 200 else []
        
        seen = load_seen()
        new_items = []
        
        for p in posts_data.get("posts", []):
            pid = p.get('id', p.get('url', str(hash(p.get('text', '')))))
            if pid not in seen:
                seen[pid] = True
                new_items.append(p)
                
        if not new_items:
            # 沒有新文章
            print("NO_NEW_ARTICLES")
            return
            
        save_seen(seen)
        
        # 準備輸出給機器人
        out = {
            "consensus": consensus,
            "signals": [{"type": s} for s in signals],
            "articles": [{"title": p.get("text", "")[:100] + "...", "link": p.get("url", "")} for p in new_items[:3]]
        }
        
        print(json.dumps(out, ensure_ascii=False))
        
    except Exception as e:
        print("NO_NEW_ARTICLES")

if __name__ == "__main__":
    main()
