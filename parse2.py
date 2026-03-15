import re, json
with open(r'c:\Users\Utente\AppData\Roaming\Kodi\addons\plugin.video.s4me\sc_watch_50489.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()
idx = html.find('data-page=')
if idx != -1:
    end_idx = html.find('>', idx)
    data_str = html[idx+11:end_idx-1]
    import html as html_lib
    data_str = html_lib.unescape(data_str)
    try:
        data = json.loads(data_str)
        t = data.get('props', {}).get('title', {})
        print(f'{t.get("name")} (ID: {t.get("id")}) - release_date: {t.get("release_date")}, last_air_date: {t.get("last_air_date")}')
    except Exception as e:
        print('Error:', e)
