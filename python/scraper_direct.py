# coding: utf-8
import sys
import os

try:
    import xbmc
    import xbmcaddon
except ImportError:
    xbmc = None
    xbmcaddon = None

from lib.tmdbscraper_direct.tmdb import TMDBMovieScraper
from lib.tmdbscraper_direct import fanarttv
from lib.tmdbscraper_direct import imdbratings
from lib.tmdbscraper_direct import traktratings

from scraper_datahelper import combine_scraped_details_info_and_ratings, \
    combine_scraped_details_available_artwork
from scraper_config import configure_scraped_details, configure_tmdb_artwork, is_fanarttv_configured

class ScraperRunner(object):
    def __init__(self, settings):
        
        self.settings = settings
        self._init_scraper()

    def _init_scraper(self):
        # Provide defaults if settings fail (e.g. mock object incomplete)
        try:
            language = self.settings.getSettingString('language')
        except:
            language = 'zh'
            
        try:
            cert_country = self.settings.getSettingString('tmdbcertcountry')
        except:
            cert_country = 'CN'
            
        try:
            search_language = self.settings.getSettingString('searchlanguage')
        except:
            search_language = language
            
        self.tmdb = TMDBMovieScraper(
            url_settings=self.settings,
            language=language,
            certification_country=cert_country,
            search_language=search_language
        )

    def search(self, title, year=None):
        """
        Run search and return raw list of dicts.
        Matches logic in scraper.py search_for_movie (strips articles, fallbacks for year)
        """
        title = self._strip_trailing_article(title)

        # Call the direct scraper search
        search_results = self.tmdb.search(title, year)
        
        if year is not None:
            if not search_results:
                search_results = self.tmdb.search(title, str(int(year)-1))
            if not search_results:
                search_results = self.tmdb.search(title, str(int(year)+1))
            if not search_results:
                search_results = self.tmdb.search(title)
        
        return search_results

    def _strip_trailing_article(self, title):
        _articles = [prefix + article for prefix in (', ', ' ') for article in ("the", "a", "an")]
        title = title.lower()
        for article in _articles:
            if title.endswith(article):
                return title[:-len(article)]
        return title

    def get_details(self, uniqueids):
        """
        Args:
            uniqueids (dict): e.g. {'tmdb': '12345', 'imdb': 'tt12345'}
        Returns:
            dict: Scraper details dict
        """
        # 1. Get Base TMDB Details
        details = self.tmdb.get_details(uniqueids)
        
        if not details or details.get('error'):
            return details
            
        # Update uniqueids with any new finding (e.g. IMDb ID found in TMDB)
        curr_uniqueids = details.get('uniqueids', {})

        # 2. Additional Artwork (Fanart.tv)
        if is_fanarttv_configured(self.settings):
            client_key = self.settings.getSettingString('fanarttv_clientkey')
            set_tmdbid = details.get('_info', {}).get('set_tmdbid')
            
            try:
                fanart_art = fanarttv.get_details(curr_uniqueids, client_key, self.tmdb.language, set_tmdbid, self.settings)
                combine_scraped_details_available_artwork(details, fanart_art, self.tmdb.language, self.settings)
            except Exception:
                pass

        # 3. Ratings (IMDb / Trakt)
        
        # Check if we should fetch IMDb
        fetch_imdb = False
        try:
            if self.settings.getSettingString('RatingS') == 'IMDb' or self.settings.getSettingBool('imdbanyway'):
                fetch_imdb = True
        except:
            pass 

        if fetch_imdb:
            try:
                imdb_res = imdbratings.get_details(curr_uniqueids, self.settings)
                combine_scraped_details_info_and_ratings(details, imdb_res)
            except:
                pass

        # Check if we should fetch Trakt
        fetch_trakt = False
        try:
            if self.settings.getSettingString('RatingS') == 'Trakt' or self.settings.getSettingBool('traktanyway'):
                fetch_trakt = True
        except:
             pass

        if fetch_trakt:
            try:
                trakt_res = traktratings.get_trakt_ratinginfo(curr_uniqueids, self.settings)
                combine_scraped_details_info_and_ratings(details, trakt_res)
            except:
                pass

        # 4. Final Configuration
        details = configure_tmdb_artwork(details, self.settings)
        details = configure_scraped_details(details, self.settings)

        return details
