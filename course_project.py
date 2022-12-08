import time
import requests
import json
import os
from tqdm import tqdm
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
TOKEN_VK = os.getenv('TOKEN_VK')
TOKEN_YA = os.getenv('TOKEN_YA')


class VkPhotos:
    url = 'https://api.vk.com/method/'
    user_id = ""
    all_albums = {}

    def __init__(self, user_id_vk, total_photos=5):
        self.total_photos = total_photos
        self.user_id_vk = user_id_vk
        self.params = {
            'access_token': TOKEN_VK,
            'v': '5.131'
        }
        self.select_max_size_photos()

    def _get_user_id(self):
        """
        запишем user_id в атрибут класса для дальнейшего использования в именовании корневых папок
        """
        VkPhotos.user_id = self.user_id_vk
        return VkPhotos.user_id

    def _get_albums(self):
        """
        получаем все альбомы, составляем словарь all_albums вида 'id': 'title'
        """
        get_albums_params = {
            'owner_id': self.user_id_vk,
            'need_system': 1
        }
        get_albums_url = self.url + "photos.getAlbums"
        req = requests.get(get_albums_url, params={**self.params, **get_albums_params}).json()
        for album in req['response']['items']:
            VkPhotos.all_albums.setdefault(album['id'], album['title'])

    def _get_data_albums(self):
        """
        проверяем есть ли доступ к альбому, если да, то обновим данные в all_albums, если нет - удаляем
        """
        self._get_albums()
        closed_albums = []
        with tqdm(total=len(VkPhotos.all_albums), ncols=80, desc="Getting albums VK", colour="blue") as pbar:
            for id, title in VkPhotos.all_albums.items():
                get_photos_params = {
                    'album_id': id,
                    'extended': 1,
                    'owner_id': self.user_id_vk
                }
                get_photos_url = self.url + "photos.get"
                req = requests.get(get_photos_url, params={**self.params, **get_photos_params})
                time.sleep(0.33)
                pbar.update(1)
                if "error" in req.json():
                    closed_albums.append(id)
                    continue
                VkPhotos.all_albums[id] = (title, req.json()['response']['items'])
        for album in closed_albums:
            VkPhotos.all_albums.pop(album)
        print(f'{len(VkPhotos.all_albums)} albums in free access. '
              f'Uploading no more than {self.total_photos} photos from each album has started.')

    def select_max_size_photos(self):
        """
        итерируемся по каждому альбому, отбирая нужное количество фото
        максимального размера, добовляем данные о них в all_albums
        """
        self._get_user_id()
        self._get_data_albums()
        for key, value in VkPhotos.all_albums.items():
            selected_photos = {}
            all_photos = value[1]
            for photo in all_photos[:self.total_photos]:
                name = photo['likes']['count']
                for photo_size in photo['sizes']:
                    if photo_size['type'] == 'w':
                        type, link = photo_size['type'], photo_size['url']
                        break
                    elif photo_size['type'] == 'z':
                        type, link = photo_size['type'], photo_size['url']
                    elif photo_size['type'] == 'x':
                        type, link = photo_size['type'], photo_size['url']
                if selected_photos.get(name):
                    selected_photos.setdefault(
                        f'{name}_{time.strftime("%d.%m.%Y", time.localtime(photo["date"]))}',
                        (type, link))
                    continue
                selected_photos.setdefault(name, (type, link))
            VkPhotos.all_albums[key] = (value[0], selected_photos)


class YaDisk:
    base_host = "https://cloud-api.yandex.net/"

    def __init__(self, token):
        self.token = token
        self.upload_to_disk()

    def _get_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"OAuth {self.token}"
        }

    def _create_dir(self, name):
        """создаем папку на Яндекс диске"""
        uri = "v1/disk/resources/"
        request_url = self.base_host + uri
        params = {"path": name}
        requests.put(request_url, params=params, headers=self._get_headers())

    def upload_to_disk(self):
        """
        загружаем фото на Яндекс диск

        предварительно создаем корневую папки с именем "id пльзователя vk",
        в ней создаются папки с именами альбомов из vk, в них загружаются фото,
        также создается локальная папка, в нее записываются json файлы с инфо
        """
        uri = "v1/disk/resources/upload/"
        request_url = self.base_host + uri
        self._create_dir(VkPhotos.user_id)
        os.mkdir(VkPhotos.user_id)
        with tqdm(total=len(VkPhotos.all_albums), ncols=80, desc="Upload to Yandex", colour="yellow") as pbar:
            for id, value in VkPhotos.all_albums.items():
                file_info_json = []
                self._create_dir(f"{VkPhotos.user_id}/{value[0]}")
                for key, val in value[1].items():
                    ya_name_file = f"{key}.jpg"
                    url_photo = val[1]
                    params = {"url": url_photo, "path": f"{VkPhotos.user_id}/{value[0]}/{ya_name_file}"}
                    response = requests.post(request_url, params=params, headers=self._get_headers())
                    time.sleep(0.33)
                    if response.status_code == 202:
                        file_info = {
                            "file_name": ya_name_file,
                            "size": val[0]
                        }
                        file_info_json.append(file_info)
                pbar.update(1)
                if file_info_json:
                    with open(f"{VkPhotos.user_id}/{value[0]}.json", "a", encoding="utf-8") as file:
                        json.dump(file_info_json, file, indent=4, ensure_ascii=False)


"""
Введите id пользователя vk (id_user_vk), вторым параметром можно задать
количество фотографий (по умолчанию 5) скачиваемых с каждого альбома,
к которому есть доступ. Токены задаются в начале программы.
"""
if __name__ == "__main__":
    id_user_vk = "1"
    vk = VkPhotos(id_user_vk, 3)
    ya = YaDisk(TOKEN_YA)

