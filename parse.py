import re, json
with open(r'c:\Users\Utente\AppData\Roaming\Kodi\addons\plugin.video.s4me\sc_search.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()
idx = html.find('data-page=')
if idx != -1:
    end_idx = html.find('>', idx)
    data_str = html[idx+11:end_idx-1]
    import html as html_lib
    data_str = html_lib.unescape(data_str)
    data = json.loads(data_str)
    titles = data.get('props', {}).get('titles', [])
    out = []
    for t in titles[:2]:
        out.append(t)
    with open('sc_titles_full.json', 'w') as outf:
        json.dump(out, outf, indent=2)
