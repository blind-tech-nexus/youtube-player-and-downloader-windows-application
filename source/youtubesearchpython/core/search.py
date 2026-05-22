import copy
from typing import Union
from urllib.parse import urlencode

from youtubesearchpython.core.requests import RequestCore
from youtubesearchpython.handlers.componenthandler import ComponentHandler
from youtubesearchpython.handlers.requesthandler import RequestHandler
from youtubesearchpython.core.constants import *

import json


class SearchCore(RequestCore, RequestHandler, ComponentHandler):
    response = None
    responseSource = None
    resultComponents = []

    def __init__(self, query: str, limit: int, language: str, region: str, searchPreferences: str, timeout: int):
        super().__init__()
        self.query = query
        self.limit = limit
        self.language = language
        self.region = region
        self.searchPreferences = searchPreferences
        self.timeout = timeout
        self.continuationKey = None
        self._channel_cache = {}
        self._playlist_cache = {}

    def sync_create(self):
        self._makeRequest()
        self._parseSource()

    def _getRequestBody(self):
        ''' Fixes #47 '''
        requestBody = copy.deepcopy(requestPayload)
        requestBody['query'] = self.query
        requestBody['client'] = {
            'hl': self.language,
            'gl': self.region,
        }
        if self.searchPreferences:
            requestBody['params'] = self.searchPreferences
        if self.continuationKey:
            requestBody['continuation'] = self.continuationKey
        self.url = 'https://www.youtube.com/youtubei/v1/search' + '?' + urlencode({
            'key': searchKey,
        })
        self.data = requestBody

    def _makeRequest(self) -> None:
        self._getRequestBody()
        request = self.syncPostRequest()
        try:
            self.response = request.text
        except Exception:
            raise Exception('ERROR: Could not make request.')

    async def _makeAsyncRequest(self) -> None:
        self._getRequestBody()
        request = await self.asyncPostRequest()
        try:
            self.response = request.text
        except Exception:
            raise Exception('ERROR: Could not make request.')

    def result(self, mode: int = ResultMode.dict) -> Union[str, dict]:
        '''Returns the search result.

        Args:
            mode (int, optional): Sets the type of result. Defaults to ResultMode.dict.

        Returns:
            Union[str, dict]: Returns JSON or dictionary.
        '''
        if mode == ResultMode.json:
            return json.dumps({'result': self.resultComponents}, indent=4)
        elif mode == ResultMode.dict:
            return {'result': self.resultComponents}

    def _next(self) -> bool:
        '''Gets the subsequent search result. Call result

        Args:
            mode (int, optional): Sets the type of result. Defaults to ResultMode.dict.

        Returns:
            Union[str, dict]: Returns True if getting more results was successful.
        '''
        if self.continuationKey:
            self.response = None
            self.responseSource = None
            self.resultComponents = []
            self._makeRequest()
            self._parseSource()
            # Guard against None responseSource after parsing
            if self.responseSource is not None:
                self._getComponents(*self.searchMode)
                return True
            return False
        else:
            return False

    async def _nextAsync(self) -> dict:
        self.response = None
        self.responseSource = None
        self.resultComponents = []
        await self._makeAsyncRequest()
        self._parseSource()
        if self.responseSource is not None:
            self._getComponents(*self.searchMode)
        return {
            'result': self.resultComponents,
        }

    def _sync_browse(self, browse_id: str) -> dict:
        previous_url = self.url
        previous_data = self.data
        try:
            self.url = 'https://www.youtube.com/youtubei/v1/browse' + '?' + urlencode({
                'key': searchKey,
            })
            request_body = copy.deepcopy(requestPayload)
            request_body['browseId'] = browse_id
            self.data = request_body
            response = self.syncPostRequest()
            return json.loads(response.text)
        finally:
            self.url = previous_url
            self.data = previous_data

    def _extract_video_count_from_channel_browse(self, response: dict) -> str:
        legacy_header_count = self._getText(self._getValue(response, ['header', 'c4TabbedHeaderRenderer', 'videosCountText']))
        if legacy_header_count and 'video' in legacy_header_count.lower():
            return legacy_header_count
        rows = self._getValue(response, ['header', 'pageHeaderRenderer', 'content', 'pageHeaderViewModel', 'metadata', 'contentMetadataViewModel', 'metadataRows']) or []
        for row in rows:
            parts = self._getValue(row, ['metadataParts']) or []
            for part in parts:
                text = self._getText(self._getValue(part, ['text']))
                if text and 'video' in text.lower():
                    return text
        return 'No videos'

    def _enrich_channel_component(self, component: dict) -> dict:
        channel_id = component.get('id')
        if not channel_id or channel_id == 'No id':
            return component
        cached = self._channel_cache.get(channel_id)
        if cached is None:
            try:
                response = self._sync_browse(channel_id)
                cached = {
                    'videoCount': self._extract_video_count_from_channel_browse(response),
                }
            except Exception:
                cached = {
                    'videoCount': component.get('videoCount') or 'No videos',
                }
            self._channel_cache[channel_id] = cached
        component['videoCount'] = cached.get('videoCount') or component.get('videoCount') or 'No videos'
        return component

    def _enrich_playlist_component(self, component: dict) -> dict:
        playlist_id = component.get('id')
        if not playlist_id or playlist_id == 'No id':
            return component
        cached = self._playlist_cache.get(playlist_id)
        if cached is None:
            try:
                response = self._sync_browse('VL' + playlist_id if not str(playlist_id).startswith('VL') else playlist_id)
                primary = self._getValue(response, ['sidebar', 'playlistSidebarRenderer', 'items', 0, 'playlistSidebarPrimaryInfoRenderer']) or {}
                secondary = self._getValue(response, ['sidebar', 'playlistSidebarRenderer', 'items', 1, 'playlistSidebarSecondaryInfoRenderer', 'videoOwner', 'videoOwnerRenderer']) or {}
                description = self._getText(self._getValue(primary, ['description']))
                view_count = self._getText(self._getValue(primary, ['stats', 1]))
                video_count = self._getText(self._getValue(primary, ['stats', 0]))
                channel_link = self._getCanonicalUrl(self._getValue(secondary, ['title', 'runs', 0, 'navigationEndpoint']))
                cached = {
                    'videoCount': video_count or component.get('videoCount') or 'No videos',
                    'viewCount': {
                        'text': view_count or 'No views',
                        'short': view_count or 'No views',
                    },
                    'descriptionSnippet': [{'text': description}] if description else component.get('descriptionSnippet') or [],
                    'channel': {
                        'id': self._getValue(secondary, ['title', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId']) or self._getValue(component, ['channel', 'id']),
                        'name': self._getText(self._getValue(secondary, ['title'])) or self._getValue(component, ['channel', 'name']),
                        'link': channel_link or self._getValue(component, ['channel', 'link']),
                        'thumbnails': self._getThumbnailSources(self._getValue(secondary, ['thumbnail'])) or self._getValue(component, ['channel', 'thumbnails']) or [],
                    }
                }
            except Exception:
                cached = {
                    'videoCount': component.get('videoCount') or 'No videos',
                    'viewCount': component.get('viewCount') or {'text': 'No views', 'short': 'No views'},
                    'descriptionSnippet': component.get('descriptionSnippet') or [],
                    'channel': component.get('channel') or {},
                }
            self._playlist_cache[playlist_id] = cached
        component['videoCount'] = cached.get('videoCount') or component.get('videoCount') or 'No videos'
        component['viewCount'] = cached.get('viewCount') or component.get('viewCount') or {'text': 'No views', 'short': 'No views'}
        component['descriptionSnippet'] = cached.get('descriptionSnippet') or component.get('descriptionSnippet') or []
        component['channel'] = cached.get('channel') or component.get('channel') or {}
        return self._finalizeComponent(component)

    def _getComponents(self, findVideos: bool, findChannels: bool, findPlaylists: bool) -> None:
        self.resultComponents = []
        # Safety: ensure responseSource is iterable
        if not self.responseSource:
            return

        def add_component(component):
            if component is None:
                return False
            if component.get('type') == 'channel':
                component = self._enrich_channel_component(component)
            elif component.get('type') == 'playlist':
                component = self._enrich_playlist_component(component)
            self.resultComponents.append(component)
            return len(self.resultComponents) >= self.limit

        for element in self.responseSource:
            if not isinstance(element, dict):
                continue

            if videoElementKey in element.keys() and findVideos:
                if add_component(self._getVideoComponent(element)):
                    break
            if channelElementKey in element.keys() and findChannels:
                if add_component(self._getChannelComponent(element)):
                    break
            if playlistElementKey in element.keys() and findPlaylists:
                if add_component(self._getPlaylistComponent(element)):
                    break
            if 'lockupViewModel' in element.keys() and findPlaylists:
                if self._getValue(element, ['lockupViewModel', 'contentType']) == 'LOCKUP_CONTENT_TYPE_PLAYLIST':
                    if add_component(self._getPlaylistComponent(element)):
                        break

            if shelfElementKey in element.keys() and findVideos:
                shelfComponent = self._getShelfComponent(element)
                if shelfComponent and isinstance(shelfComponent, dict):
                    elements = shelfComponent.get('elements')
                    if elements and hasattr(elements, '__iter__'):
                        for shelfElement in elements:
                            if shelfElement and isinstance(shelfElement, dict):
                                if add_component(self._getVideoComponent(shelfElement, shelfTitle=shelfComponent.get('title'))):
                                    break
                    if len(self.resultComponents) >= self.limit:
                        break

            if richItemKey in element.keys() and findVideos:
                richItemElement = self._getValue(element, [richItemKey, 'content'])
                if richItemElement and isinstance(richItemElement, dict):
                    if videoElementKey in richItemElement.keys():
                        if add_component(self._getVideoComponent(richItemElement)):
                            break

            if 'gridShelfViewModel' in element.keys() and findVideos:
                for short_component in self._getGridShelfComponents(element):
                    if add_component(short_component):
                        break

            if len(self.resultComponents) >= self.limit:
                break
