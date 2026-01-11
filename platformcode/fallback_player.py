# -*- coding: utf-8 -*-
"""
Sistema di playback con fallback tra canali S4ME.
"""
import sys
from platformcode import config, logger, platformtools
from core.item import Item

PY3 = sys.version_info[0] >= 3

TMDB_API_KEY = 'a1ab8b8669da03637a4b98fa39c39228'

def fetch_movie_info_from_tmdb(tmdb_id):
    """
    Fetch movie title and year from TMDb API.
    
    Args:
        tmdb_id: TMDb movie ID
    
    Returns:
        tuple: (title, year) or (None, None) if failed
    """
    try:
        from core import httptools
        import json
        
        url = f'https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}&language=it'
        response = httptools.downloadpage(url)
        
        if response.code == 200:
            data = json.loads(response.data)
            title = data.get('title', '')
            release_date = data.get('release_date', '')
            year = release_date[:4] if release_date else ''
            return title, year
    except Exception as e:
        logger.error(f'fetch_movie_info_from_tmdb error: {e}')
    
    return None, None

def fetch_tvshow_info_from_tmdb(tmdb_id):
    """
    Fetch TV show title and year from TMDb API.
    
    Args:
        tmdb_id: TMDb TV show ID
    
    Returns:
        tuple: (title, year) or (None, None) if failed
    """
    try:
        from core import httptools
        import json
        
        url = f'https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}&language=it'
        response = httptools.downloadpage(url)
        
        if response.code == 200:
            data = json.loads(response.data)
            title = data.get('name', '')
            first_air_date = data.get('first_air_date', '')
            year = first_air_date[:4] if first_air_date else ''
            return title, year
    except Exception as e:
        logger.error(f'fetch_tvshow_info_from_tmdb error: {e}')
    
    return None, None


def play_movie_fallback(item):
    """
    Riproduce un film provando tutti i canali configurati in ordine.
    
    Args:
        item: Item con text (titolo), year, e metadati opzionali
    """
    from platformcode.channel_utils import get_fallback_order, get_channel_name
    
    title = item.text if item.text else ''
    year = str(item.year) if item.year else ''
    
    # Always fetch title from TMDb when tmdb_id is available (URL parsing is unreliable with special chars like &)
    tmdb_id = getattr(item, 'tmdb_id', None)
    if tmdb_id:
        logger.info(f'Fetching movie info from TMDb ID: {tmdb_id}')
        fetched_title, fetched_year = fetch_movie_info_from_tmdb(tmdb_id)
        if fetched_title:
            title = fetched_title
            if fetched_year:
                year = fetched_year
            logger.info(f'Using TMDb info: {title} ({year})')
    
    # Estrai metadati extra se presenti
    metadata = {}
    if hasattr(item, 'imdb_id') and item.imdb_id: metadata['imdb_id'] = item.imdb_id
    if hasattr(item, 'tmdb_id') and item.tmdb_id: metadata['tmdb_id'] = item.tmdb_id
    if hasattr(item, 'plot') and item.plot: metadata['plot'] = item.plot
    if hasattr(item, 'duration') and item.duration: metadata['duration'] = item.duration
    
    if not title:
        platformtools.dialog_notification(config.get_localized_string(20000), 'Titolo mancante')
        return
    
    channels = get_fallback_order('movie')
    
    if not channels:
        platformtools.dialog_notification(config.get_localized_string(20000), 'Nessun canale configurato')
        return
    
    logger.info(f'play_movie_fallback: {title} ({year}) - Channels: {channels}')
    
    # Progress dialog
    progress = platformtools.dialog_progress_bg(
        config.get_localized_string(20000),
        f'Cercando: {title}'
    )
    
    try:
        for i, channel_id in enumerate(channels):
            channel_name = get_channel_name(channel_id)
            progress.update(int((i / len(channels)) * 100), f'Provando: {channel_name}')
            
            logger.info(f'Trying channel: {channel_id}')
            
            result = try_channel_movie(channel_id, title, year, metadata)
            
            if result:
                progress.close()
                logger.info(f'Found on channel: {channel_id}')
                return
        
        # Nessun canale ha funzionato
        progress.close()
        platformtools.dialog_notification(
            config.get_localized_string(20000),
            'Film non trovato su nessun canale'
        )
        try:
            import sys
            import xbmcplugin
            import xbmcgui
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
        except:
            pass
        
    except Exception as e:
        progress.close()
        logger.error(f'play_movie_fallback error: {e}')
        import traceback
        logger.error(traceback.format_exc())


def play_episode_fallback(item):
    """
    Riproduce un episodio provando tutti i canali configurati in ordine.
    
    Args:
        item: Item con text (titolo serie), season, episode, year, e metadati opzionali
    """
    from platformcode.channel_utils import get_fallback_order, get_channel_name
    
    title = item.text if item.text else ''
    season = int(item.season) if item.season else 1
    episode = int(item.episode) if item.episode else 1
    year = str(item.year) if item.year else ''
    
    # Always fetch title from TMDb when tmdb_id is available (URL parsing is unreliable with special chars like &)
    tmdb_id = getattr(item, 'tmdb_id', None)
    if tmdb_id:
        logger.info(f'Fetching TV show info from TMDb ID: {tmdb_id}')
        fetched_title, fetched_year = fetch_tvshow_info_from_tmdb(tmdb_id)
        if fetched_title:
            title = fetched_title
            if fetched_year:
                year = fetched_year
            logger.info(f'Using TMDb info: {title} ({year})')
    
    
    # Estrai metadati extra se presenti (cruciali per UpNext)
    metadata = {}
    if hasattr(item, 'imdb_id') and item.imdb_id: metadata['imdb_id'] = item.imdb_id
    if hasattr(item, 'tmdb_id') and item.tmdb_id: metadata['tmdb_id'] = item.tmdb_id
    if hasattr(item, 'tvshowtitle') and item.tvshowtitle: metadata['tvshowtitle'] = item.tvshowtitle
    else: metadata['tvshowtitle'] = title # Fallback
    
    if hasattr(item, 'plot') and item.plot: metadata['plot'] = item.plot
    if hasattr(item, 'duration') and item.duration: metadata['duration'] = item.duration
    if hasattr(item, 'date') and item.date: metadata['premiered'] = item.date
    if hasattr(item, 'title') and item.title: metadata['title'] = item.title # Titolo episodio
    
    logger.info(f"play_episode_fallback initial metadata: {metadata}")
    
    if not title:
        platformtools.dialog_notification(config.get_localized_string(20000), 'Titolo mancante')
        return
    
    channels = get_fallback_order('tvshow')
    
    if not channels:
        platformtools.dialog_notification(config.get_localized_string(20000), 'Nessun canale configurato')
        return
    
    logger.info(f'play_episode_fallback: {title} S{season}E{episode} - Channels: {channels}')
    
    # Progress dialog
    progress = platformtools.dialog_progress_bg(
        config.get_localized_string(20000),
        f'Cercando: {title} S{season}E{episode}'
    )
    
    try:
        for i, channel_id in enumerate(channels):
            channel_name = get_channel_name(channel_id)
            progress.update(int((i / len(channels)) * 100), f'Provando: {channel_name}')
            
            logger.info(f'Trying channel: {channel_id}')
            
            result = try_channel_episode(channel_id, title, season, episode, year, metadata)
            
            if result:
                progress.close()
                logger.info(f'Found on channel: {channel_id}')
                return
        
        # Nessun canale ha funzionato
        progress.close()
        platformtools.dialog_notification(
            config.get_localized_string(20000),
            'Episodio non trovato su nessun canale'
        )
        try:
            import sys
            import xbmcplugin
            import xbmcgui
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
        except:
            pass
        
    except Exception as e:
        progress.close()
        logger.error(f'play_episode_fallback error: {e}')
        import traceback
        logger.error(traceback.format_exc())


def try_channel_movie(channel_id, title, year, metadata=None):
    """
    Prova a trovare e riprodurre un film su un canale specifico.
    Verifica i link uno alla volta e passa al prossimo canale se tutti sono morti.
    """
    from platformcode.launcher import importChannel, new_search
    from core import servertools
    from platformcode import platformtools
    
    try:
        channel = importChannel(Item(channel=channel_id))
        if not channel:
            return False
        
        # Cerca il film
        search_item = Item(
            channel=channel_id,
            action='search',
            infoLabels={'mediatype': 'movie'}
        )
        search_item.fast_search = True
        
        results = new_search(search_item.clone(text=title), channel)
        
        if not results:
            return False
        
        # Trova il match migliore
        best_match = find_best_movie_match(results, title, year)
        
        if not best_match:
            return False
        
        logger.info(f'Match found: {best_match.contentTitle or best_match.title}')
        
        # Ottieni la lista dei video dal canale
        video_items = []
        if hasattr(channel, 'findvideos'):
            video_items = channel.findvideos(best_match)
        
        if not video_items:
            logger.info(f'No videos found on {channel_id}')
            return False
        
        # Filtra solo gli item con server definito
        video_items = [v for v in video_items if hasattr(v, 'server') and v.server]
        
        if not video_items:
            logger.info(f'No valid video items on {channel_id}')
            return False
        
        # Prova ogni video item fino a trovarne uno funzionante
        for video_item in video_items:
            try:
                # Verifica se il video esiste (risolve anche gli shortener)
                video_urls, exists, error_msg = servertools.resolve_video_urls_for_playing(
                    video_item.server, 
                    video_item.url, 
                    video_item.password if hasattr(video_item, 'password') else '',
                    muestra_dialogo=False
                )
                
                if exists and video_urls:
                    # Video funzionante trovato! Riproducilo
                    logger.info(f'Working link found on {channel_id}: {video_item.server}')
                    
                    # Passa gli URL pre-risolti per evitare doppia risoluzione
                    video_item.video_urls = video_urls
                    
                    # Applica metadati
                    if metadata:
                        video_item.infoLabels.update(metadata)
                    
                    # Riproduci
                    platformtools.play_video(video_item)
                    return True
                else:
                    logger.info(f'Dead link on {channel_id}: {video_item.server} - {error_msg}')
                    # Prova il prossimo video item
                    
            except Exception as e:
                logger.info(f'Error checking link on {channel_id}: {e}')
                continue
        
        # Tutti i link sono morti
        logger.info(f'All links dead on {channel_id}, trying next channel')
        return False
        
    except Exception as e:
        logger.error(f'try_channel_movie error on {channel_id}: {e}')
        import traceback
        logger.error(traceback.format_exc())
        return False


def try_channel_episode(channel_id, title, season, episode, year, metadata=None):
    """
    Prova a trovare e riprodurre un episodio su un canale specifico.
    Verifica i link uno alla volta e passa al prossimo canale se tutti sono morti.
    """
    from platformcode.launcher import importChannel, new_search
    from core import servertools
    from platformcode import platformtools
    
    try:
        channel = importChannel(Item(channel=channel_id))
        if not channel:
            return False
        
        # Cerca la serie
        search_item = Item(
            channel=channel_id,
            action='search',
            infoLabels={'mediatype': 'tvshow'}
        )
        search_item.fast_search = True
        
        results = new_search(search_item.clone(text=title), channel)
        
        if not results:
            return False
        
        # Trova il match migliore per la serie
        best_match = find_best_tvshow_match(results, title, year)
        
        if not best_match:
            return False
        
        logger.info(f'Show match found: {best_match.contentSerieName or best_match.title}')
        
        # Trova l'episodio specifico
        target_episode = None
        
        # Prova find_episode ottimizzato se disponibile
        if hasattr(channel, 'find_episode'):
            target_episode = channel.find_episode(best_match, season, episode)
        
        # Fallback: cerca tra tutti gli episodi
        if not target_episode:
            episodes = []
            if hasattr(channel, 'episodios'):
                episodes = channel.episodios(best_match)
            elif hasattr(channel, 'episodes'):
                episodes = channel.episodes(best_match)
            
            for ep in episodes:
                ep_season = ep.contentSeason or ep.infoLabels.get('season', 0)
                ep_number = ep.contentEpisodeNumber or ep.infoLabels.get('episode', 0)
                
                if int(ep_season) == season and int(ep_number) == episode:
                    target_episode = ep
                    break
        
        if not target_episode:
            logger.info(f'Episode S{season}E{episode} not found on {channel_id}')
            return False
        
        logger.info(f'Episode found: S{season}E{episode}')
        
        # Ottieni la lista dei video dal canale
        video_items = []
        if hasattr(channel, 'findvideos'):
            video_items = channel.findvideos(target_episode)
        
        if not video_items:
            logger.info(f'No videos found for episode on {channel_id}')
            return False
        
        # Filtra solo gli item con server definito
        video_items = [v for v in video_items if hasattr(v, 'server') and v.server]
        
        if not video_items:
            logger.info(f'No valid video items for episode on {channel_id}')
            return False
        
        # Prova ogni video item fino a trovarne uno funzionante
        for video_item in video_items:
            try:
                # Verifica se il video esiste (risolve anche gli shortener)
                video_urls, exists, error_msg = servertools.resolve_video_urls_for_playing(
                    video_item.server, 
                    video_item.url, 
                    video_item.password if hasattr(video_item, 'password') else '',
                    muestra_dialogo=False
                )
                
                if exists and video_urls:
                    # Video funzionante trovato!
                    logger.info(f'Working episode link found on {channel_id}: {video_item.server}')
                    
                    # Passa gli URL pre-risolti
                    video_item.video_urls = video_urls
                    
                    # Applica metadata
                    if metadata:
                        if 'duration' in metadata:
                           try:
                               metadata['duration'] = int(metadata['duration'])
                           except:
                               del metadata['duration']
                        video_item.infoLabels.update(metadata)
                    
                    # Assicurati che i label base ci siano
                    if not video_item.infoLabels.get('mediatype'):
                        video_item.infoLabels['mediatype'] = 'episode'
                    if not video_item.infoLabels.get('season'):
                        video_item.infoLabels['season'] = season
                    if not video_item.infoLabels.get('episode'):
                        video_item.infoLabels['episode'] = episode
                    
                    # UpNext Integration
                    try:
                        import xbmc
                        import json
                        
                        if PY3:
                            from urllib.parse import urlencode
                        else:
                            from urllib import urlencode
                        
                        current_season = int(video_item.infoLabels.get('season', season))
                        current_episode = int(video_item.infoLabels.get('episode', episode))
                        
                        next_season = current_season
                        next_episode = current_episode + 1
                        
                        url_params = {
                            'action': 'play_episode_fallback',
                            'text': title,
                            'season': next_season,
                            'episode': next_episode,
                            'year': year
                        }
                        
                        if metadata:
                            for key, value in metadata.items():
                                if key not in ['title', 'plot', 'duration', 'premiered', 'date', 'votes', 'rating', 'playcount']:
                                    if value:
                                        url_params[key] = value
                        
                        query = urlencode(url_params)
                        next_url = f"plugin://plugin.video.s4me/?{query}"
                        
                        pseudo_show_id = metadata.get('tmdb_id') or metadata.get('imdb_id') or str(abs(hash(title))) if metadata else str(abs(hash(title)))
                        
                        upnext_info = {
                            "current_episode": {
                                "episode": str(current_episode),
                                "season": str(current_season),
                                "title": title,
                                "showtitle": metadata.get('tvshowtitle', title) if metadata else title,
                                "tvshowid": pseudo_show_id,
                                "mediatype": "episode",
                                "art": {
                                    "tvshow.poster": video_item.infoLabels.get('poster') or video_item.thumbnail,
                                    "thumb": video_item.thumbnail,
                                    "fanart": video_item.fanart
                                }
                            },
                            "next_episode": {
                                "episode": str(next_episode),
                                "season": str(next_season),
                                "title": "Episode {}".format(next_episode),
                                "showtitle": metadata.get('tvshowtitle', title) if metadata else title,
                                "tvshowid": pseudo_show_id,
                                "mediatype": "episode",
                                "art": {
                                    "tvshow.poster": video_item.infoLabels.get('poster') or video_item.thumbnail,
                                    "thumb": video_item.thumbnail,
                                    "fanart": video_item.fanart
                                }
                            },
                            "play_url": next_url,
                        }
                        
                        def send_upnext_signal(data):
                            import time
                            import base64
                            
                            idx = 0
                            while idx < 20:
                                if xbmc.Player().isPlaying():
                                    break
                                time.sleep(1)
                                idx += 1
                            
                            time.sleep(5)
                            
                            if xbmc.Player().isPlaying():
                                try:
                                    json_data = json.dumps(data)
                                    encoded_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
                                    
                                    params = {
                                        "sender": "plugin.video.s4me.SIGNAL",
                                        "message": "upnext_data",
                                        "data": [encoded_data]
                                    }
                                    
                                    xbmc.executeJSONRPC(json.dumps({
                                        "jsonrpc": "2.0", 
                                        "method": "JSONRPC.NotifyAll", 
                                        "params": params, 
                                        "id": 1
                                    }))
                                except Exception as e:
                                    logger.error(f"[S4ME] UpNext thread error: {e}")
                        
                        import threading
                        t = threading.Thread(target=send_upnext_signal, args=(upnext_info,))
                        t.daemon = True
                        t.start()
                        
                    except Exception as e:
                        logger.error(f"[S4ME] UpNext integration failed: {e}")
                    
                    # Riproduci
                    platformtools.play_video(video_item)
                    return True
                else:
                    logger.info(f'Dead episode link on {channel_id}: {video_item.server} - {error_msg}')
                    
            except Exception as e:
                logger.info(f'Error checking episode link on {channel_id}: {e}')
                continue
        
        # Tutti i link sono morti
        logger.info(f'All episode links dead on {channel_id}, trying next channel')
        return False
        
    except Exception as e:
        logger.error(f'try_channel_episode error on {channel_id}: {e}')
        import traceback
        logger.error(traceback.format_exc())
        return False





def normalize_title(title):
    """Pulisce il titolo per il confronto."""
    import re
    if not title: return ''
    # Rimuovi accenti e caratteri speciali
    title = title.lower().strip()
    # Rimuovi tutto tranne alfanumerici e spazi
    title = re.sub(r'[^a-z0-9\s]', '', title)
    # Collassa spazi multipli in uno singolo
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def find_best_movie_match(results, title, year):
    """
    Trova il miglior match per un film con logica rigorosa.
    RETURN: Item o None. Se None, passa al prossimo canale.
    """
    import re
    
    clean_search_title = normalize_title(title)
    search_year = int(year) if year and str(year).isdigit() else 0
    
    logger.info(f"Seeking Movie: '{clean_search_title}' ({search_year})")
    
    candidates = []
    
    for result in results:
        if result.contentType != 'movie':
            continue
        
        res_title = normalize_title(result.contentTitle or result.title or '')
        res_original_title = normalize_title(result.infoLabels.get('originaltitle', ''))
        
        # Gestione anno
        res_year_str = str(result.year or result.infoLabels.get('year', ''))
        # Estrai anno se ci sono date complete (YYYY-MM-DD)
        match_year = re.search(r'(\d{4})', res_year_str)
        res_year = int(match_year.group(1)) if match_year else 0
        
        # Calcola differenza di anno
        year_diff = abs(search_year - res_year) if (search_year and res_year) else 100
        
        logger.info(f"CHECK CANDIDATE: '{res_title}' ({res_year}) vs '{clean_search_title}' ({search_year}) | Diff: {year_diff}")
        
        # CRITERIO 0: Skip se l'anno è sicuramente sbagliato (>1 anno diff)
        # MA solo se entrambi gli anni sono presenti.
        if search_year and res_year and year_diff > 1:
            logger.info("-> REJECT: Year mismatch")
            continue

        # CRITERIO 1: Match Esatto Titolo
        if clean_search_title == res_title:
            if year_diff <= 1 and (search_year or res_year):
                logger.info("-> MATCH EXACT TITLE+YEAR")
                return result
            logger.info("-> CANDIDATE ADDED: Exact Title (Year Uncertain)")
            candidates.append(result)
            
        # CRITERIO 2: Match Titolo Originale
        elif clean_search_title == res_original_title and res_original_title:
            if year_diff <= 1 and (search_year or res_year):
                logger.info("-> MATCH ORIGINAL TITLE+YEAR")
                return result
            logger.info("-> CANDIDATE ADDED: Exact Original Title (Year Uncertain)")
            candidates.append(result)
            
        # CRITERIO 3: Se titolo molto lungo, concessa un po' più di tolleranza
        elif len(clean_search_title) > 10 and clean_search_title in res_title:
             if year_diff == 0 and search_year:
                logger.info("-> CANDIDATE ADDED: Partial Title + Exact Year")
                candidates.append(result)

    # Se abbiamo un solo candidato, lo prendiamo
    if candidates:
        if len(candidates) == 1:
            logger.info("-> SINGLE CANDIDATE SELECTED")
            return candidates[0]
            
        # Se ne abbiamo più di uno, se c'è un anno cerchiamo il più vicino
        if search_year:
            candidates.sort(key=lambda x: abs(search_year - (int(re.search(r'(\d{4})', str(x.year)).group(1)) if re.search(r'(\d{4})', str(x.year)) else 0)))
            logger.info("-> BEST YEAR FINAL CANDIDATE SELECTED")
            return candidates[0]
            
        # Se non c'è anno di ricerca, e abbiamo più candidati con lo stesso titolo... prendiamo il primo?
        # O quello con l'anno più recente?
        logger.info("-> FIRST CANDIDATE SELECTED (No Year Filter)")
        return candidates[0]
            
    # Nessun match sicuro trovato
    logger.info("-> NO MATCH FOUND")
    return None


def find_best_tvshow_match(results, title, year):
    """
    Trova il miglior match per una serie TV con logica rigorosa.
    """
    import re
    
    clean_search_title = normalize_title(title)
    search_year = int(year) if year and str(year).isdigit() else 0
    
    logger.info(f"Seeking TVShow: '{clean_search_title}' ({search_year})")
    
    candidates = []
    
    for result in results:
        if result.contentType != 'tvshow':
            continue
            
        res_title = normalize_title(result.contentSerieName or result.contentTitle or result.title or '')
        res_original_title = normalize_title(result.infoLabels.get('originaltitle', ''))
        
        res_year_str = str(result.year or result.infoLabels.get('year', ''))
        match_year = re.search(r'(\d{4})', res_year_str)
        res_year = int(match_year.group(1)) if match_year else 0
        
        year_diff = abs(search_year - res_year) if (search_year and res_year) else 100
        
        logger.info(f"CHECK TV CANDIDATE: '{res_title}' ({res_year}) vs '{clean_search_title}' ({search_year}) | Diff: {year_diff}")
        
        # Skip se l'anno è completamente diverso (> 2 anni) per evitare remake/omonimi
        if search_year and res_year and year_diff > 2:
            logger.info("-> SKIP YEAR DIFF")
            continue
        
        # CRITERIO 1: Match Esatto Titolo
        if clean_search_title == res_title:
            # Se abbiamo l'anno, preferiamo quello vicino
            if year_diff <= 1: 
                logger.info("-> MATCH EXACT TITLE+YEAR")
                return result
            candidates.append(result)
            
        # CRITERIO 2: Match Titolo Originale
        elif clean_search_title == res_original_title and res_original_title:
             if year_diff <= 1: 
                logger.info("-> MATCH ORIGINAL TITLE+YEAR")
                return result
             candidates.append(result)
    
    # Se abbiamo trovato candidati col titolo giusto ma anno incerto
    if candidates:
        # Se c'è solo un candidato, prendiamo quello
        if len(candidates) == 1:
            return candidates[0]
            
        # Se ce ne sono più di uno, cerchiamo quello con l'anno più vicino
        candidates.sort(key=lambda x: abs(search_year - (int(re.search(r'(\d{4})', str(x.year)).group(1)) if re.search(r'(\d{4})', str(x.year)) else 0)))
        return candidates[0]
            
    return None




