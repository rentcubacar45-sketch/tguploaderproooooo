import requests
import os
import textwrap
import re
import json
import urllib
from bs4 import BeautifulSoup
import requests_toolbelt as rt
from requests_toolbelt import MultipartEncoderMonitor
from requests_toolbelt import MultipartEncoder
from functools import partial
import uuid
import time
from ProxyCloud import ProxyCloud
import socket
import socks
import asyncio
import threading
import S5Crypto
from datetime import datetime


class CallingUpload:
    def __init__(self, func, filename, args):
        self.func = func
        self.args = args
        self.filename = filename
        self.time_start = time.time()
        self.time_total = 0
        self.speed = 0
        self.last_read_byte = 0
    
    def __call__(self, monitor):
        try:
            self.speed += monitor.bytes_read - self.last_read_byte
            self.last_read_byte = monitor.bytes_read
            tcurrent = time.time() - self.time_start
            self.time_total += tcurrent
            self.time_start = time.time()
            if self.time_total >= 1:
                clock_time = (monitor.len - monitor.bytes_read) / (self.speed)
                if self.func:
                    self.func(self.filename, monitor.bytes_read, monitor.len, self.speed, clock_time, self.args)
                self.time_total = 0
                self.speed = 0
        except:
            pass


class MoodleClient(object):
    def __init__(self, user, passw, host='', repo_id=4, proxy: ProxyCloud = None):
        self.username = user
        self.password = passw
        self.session = requests.Session()
        self.path = 'https://moodle.uclv.edu.cu/'
        self.host_tokenize = 'https://tguploader.url/'
        if host != '':
            self.path = host
        self.userdata = None
        self.userid = ''
        self.repo_id = repo_id
        self.sesskey = ''
        self.proxy = None
        if proxy:
            self.proxy = proxy.as_dict_proxy()
        self.baseheaders = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:99.0) Gecko/20100101 Firefox/99.0'}

    def getsession(self):
        return self.session

    def getUserData(self):
        try:
            tokenUrl = self.path + 'login/token.php?service=moodle_mobile_app&username=' + urllib.parse.quote(
                self.username) + '&password=' + urllib.parse.quote(self.password)
            resp = self.session.get(tokenUrl, proxies=self.proxy, headers=self.baseheaders)
            data = self.parsejson(resp.text)
            data['s5token'] = S5Crypto.tokenize([self.username, self.password])
            return data
        except:
            return None

    def getDirectUrl(self, url):
        tokens = str(url).split('/')
        direct = self.path + 'webservice/pluginfile.php/' + tokens[4] + '/user/private/' + tokens[-1] + '?token=' + \
                 self.data['token']
        return direct

    def getSessKey(self):
        fileurl = self.path + 'my/#'
        resp = self.session.get(fileurl, proxies=self.proxy, headers=self.baseheaders)
        soup = BeautifulSoup(resp.text, 'html.parser')
        sesskey = soup.find('input', attrs={'name': 'sesskey'})['value']
        return sesskey

    def login(self):
        try:
            login = self.path + 'login/index.php'
            resp = self.session.get(login, proxies=self.proxy, headers=self.baseheaders)
            cookie = resp.cookies.get_dict()
            soup = BeautifulSoup(resp.text, 'html.parser')
            anchor = ''
            try:
                anchor = soup.find('input', attrs={'name': 'anchor'})['value']
            except:
                pass
            logintoken = ''
            try:
                logintoken = soup.find('input', attrs={'name': 'logintoken'})['value']
            except:
                pass
            username = self.username
            password = self.password
            payload = {'anchor': '', 'logintoken': logintoken, 'username': username, 'password': password,
                       'rememberusername': 1}
            loginurl = self.path + 'login/index.php'
            resp2 = self.session.post(loginurl, data=payload, proxies=self.proxy, headers=self.baseheaders)
            soup = BeautifulSoup(resp2.text, 'html.parser')
            counter = 0
            for i in resp2.text.splitlines():
                if "loginerrors" in i or (0 < counter <= 3):
                    counter += 1
                    print(i)
            if counter > 0:
                print('No pude iniciar sesion')
                return False
            else:
                try:
                    self.userid = soup.find('div', {'id': 'nav-notification-popover-container'})['data-userid']
                except:
                    try:
                        self.userid = soup.find('a', {'title': 'Enviar un mensaje'})['data-userid']
                    except:
                        pass
                print('E iniciado sesion con exito')
                self.userdata = self.getUserData()
                try:
                    self.sesskey = self.getSessKey()
                except:
                    pass
                return True
        except Exception as ex:
            pass
        return False

    def createEvidence(self, name, desc=''):
        evidenceurl = self.path + 'admin/tool/lp/user_evidence_edit.php?userid=' + self.userid
        resp = self.session.get(evidenceurl, proxies=self.proxy, headers=self.baseheaders)
        soup = BeautifulSoup(resp.text, 'html.parser')

        sesskey = self.sesskey
        files = self.extractQuery(soup.find('object')['data'])['itemid']

        saveevidence = self.path + 'admin/tool/lp/user_evidence_edit.php?id=&userid=' + self.userid + '&return='
        payload = {'userid': self.userid,
                   'sesskey': sesskey,
                   '_qf__tool_lp_form_user_evidence': 1,
                   'name': name, 'description[text]': desc,
                   'description[format]': 1,
                   'url': '',
                   'files': files,
                   'submitbutton': 'Guardar+cambios'}
        resp = self.session.post(saveevidence, data=payload, proxies=self.proxy, headers=self.baseheaders)

        evidenceid = str(resp.url).split('?')[1].split('=')[1]

        return {'name': name, 'desc': desc, 'id': evidenceid, 'url': resp.url, 'files': []}

    def createBlog(self, name, itemid, desc="<p+dir=\"ltr\"+style=\"text-align:+left;\">asd<br></p>"):
        post_attach = f'{self.path}blog/edit.php?action=add&userid=' + self.userid
        resp = self.session.get(post_attach, proxies=self.proxy, headers=self.baseheaders)
        soup = BeautifulSoup(resp.text, 'html.parser')
        attachment_filemanager = soup.find('input', {'id': 'id_attachment_filemanager'})['value']
        post_url = f'{self.path}blog/edit.php'
        payload = {'action': 'add',
                   'entryid': '',
                   'modid': 0,
                   'courseid': 0,
                   'sesskey': self.sesskey,
                   '_qf__blog_edit_form': 1,
                   'mform_isexpanded_id_general': 1,
                   'mform_isexpanded_id_tagshdr': 1,
                   'subject': name,
                   'summary_editor[text]': desc,
                   'summary_editor[format]': 1,
                   'summary_editor[itemid]': itemid,
                   'attachment_filemanager': attachment_filemanager,
                   'publishstate': 'site',
                   'tags': '_qf__force_multiselect_submission',
                   'submitbutton': 'Guardar+cambios'}
        resp = self.session.post(post_url, data=payload, proxies=self.proxy, headers=self.baseheaders)
        return resp

    def create_event_from_url(self, file_name, file_url):
        """
        Crea un evento en el calendario a partir de un archivo ya subido
        
        Args:
            file_name: Nombre del archivo
            file_url: URL del archivo ya subido
        
        Returns:
            Diccionario con información del evento creado
        """
        try:
            # Obtener fecha y hora actual
            now = datetime.now()
            
            # Crear descripción con el enlace al archivo
            description = f'<p dir="ltr" style="text-align: left;">'
            description += f'<strong>📄 Archivo:</strong> {file_name}<br>'
            description += f'<strong>🔗 Enlace:</strong> <a href="{file_url}" target="_blank">Abrir archivo</a><br>'
            description += f'<strong>📅 Subido:</strong> {now.strftime("%d/%m/%Y %H:%M")}<br>'
            description += f'</p>'
            
            # Codificar para URL
            description_encoded = urllib.parse.quote(description)
            name_encoded = urllib.parse.quote(file_name)
            
            # Preparar datos del formulario
            form_data = f"id=0&userid={self.userid}&modulename=&instance=0&visible=1&eventtype=user"
            form_data += f"&sesskey={self.sesskey}"
            form_data += f"&_qf__core_calendar_local_event_forms_create=1&mform_showmore_id_general=1"
            form_data += f"&name={name_encoded}"
            form_data += f"&timestart%5Bday%5D={now.day}&timestart%5Bmonth%5D={now.month}"
            form_data += f"&timestart%5Byear%5D={now.year}"
            form_data += f"&timestart%5Bhour%5D={now.hour}&timestart%5Bminute%5D={now.minute}"
            form_data += f"&description%5Btext%5D={description_encoded}"
            form_data += f"&description%5Bformat%5D=1"
            form_data += f"&description%5Bitemid%5D={int(time.time())}"
            form_data += f"&location=&duration=0"
            
            # URL para crear evento
            event_url = f'{self.path}lib/ajax/service.php?sesskey={self.sesskey}&info=core_calendar_submit_create_update_form'
            
            # JSON para la petición AJAX
            jsondata = [{
                "index": 0,
                "methodname": "core_calendar_submit_create_update_form",
                "args": {"formdata": form_data}
            }]
            
            # Headers
            headers = {
                'Content-type': 'application/json',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                **self.baseheaders
            }
            
            # Enviar petición
            resp = self.session.post(event_url, json=jsondata, headers=headers, proxies=self.proxy)
            
            # Procesar respuesta
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    if 'error' in data[0] and data[0]['error']:
                        print(f"Error creando evento: {data[0]['error']}")
                        return None
                    elif 'data' in data[0] and data[0]['data']:
                        print(f"✅ Evento creado exitosamente: {file_name}")
                        return data[0]['data']
            
            return None
            
        except Exception as e:
            print(f"❌ Error creando evento: {str(e)}")
            return None

    def saveEvidence(self, evidence):
        evidenceurl = self.path + 'admin/tool/lp/user_evidence_edit.php?id=' + evidence['id'] + '&userid=' + self.userid + '&return=list'
        resp = self.session.get(evidenceurl, proxies=self.proxy, headers=self.baseheaders)
        soup = BeautifulSoup(resp.text, 'html.parser')
        sesskey = soup.find('input', attrs={'name': 'sesskey'})['value']
        files = evidence['files']
        saveevidence = self.path + 'admin/tool/lp/user_evidence_edit.php?id=' + evidence['id'] + '&userid=' + self.userid + '&return=list'
        payload = {'userid': self.userid,
                   'sesskey': sesskey,
                   '_qf__tool_lp_form_user_evidence': 1,
                   'name': evidence['name'], 'description[text]': evidence['desc'],
                   'description[format]': 1, 'url': '',
                   'files': files,
                   'submitbutton': 'Guardar+cambios'}
        resp = self.session.post(saveevidence, data=payload, proxies=self.proxy, headers=self.baseheaders)
        return evidence

    def getEvidences(self):
        evidencesurl = self.path + 'admin/tool/lp/user_evidence_list.php?userid=' + self.userid
        resp = self.session.get(evidencesurl, proxies=self.proxy, headers=self.baseheaders)
        soup = BeautifulSoup(resp.text, 'html.parser')
        nodes = soup.find_all('tr', {'data-region': 'user-evidence-node'})
        list = []
        for n in nodes:
            nodetd = n.find_all('td')
            evurl = nodetd[0].find('a')['href']
            evname = n.find('a').next
            evid = evurl.split('?')[1].split('=')[1]
            nodefiles = nodetd[1].find_all('a')
            nfilelist = []
            for f in nodefiles:
                url = str(f['href'])
                directurl = url
                try:
                    directurl = url + '&token=' + self.userdata['token']
                    directurl = str(directurl).replace('pluginfile.php', 'webservice/pluginfile.php')
                except:
                    pass
                nfilelist.append({'name': f.next, 'url': url, 'directurl': directurl})
            list.append({'name': evname, 'desc': '', 'id': evid, 'url': evurl, 'files': nfilelist})
        return list

    def deleteEvidence(self, evidence):
        evidencesurl = self.path + 'admin/tool/lp/user_evidence_edit.php?userid=' + self.userid
        resp = self.session.get(evidencesurl, proxies=self.proxy, headers=self.baseheaders)
        soup = BeautifulSoup(resp.text, 'html.parser')
        sesskey = soup.find('input', attrs={'name': 'sesskey'})['value']
        deleteUrl = self.path + 'lib/ajax/service.php?sesskey=' + sesskey + '&info=core_competency_delete_user_evidence,tool_lp_data_for_user_evidence_list_page'
        savejson = [{"index": 0, "methodname": "core_competency_delete_user_evidence", "args": {"id": evidence['id']}},
                    {"index": 1, "methodname": "tool_lp_data_for_user_evidence_list_page",
                     "args": {"userid": self.userid}}]
        headers = {'Content-type': 'application/json', 'Accept': 'application/json, text/javascript, */*; q=0.01',
                   **self.baseheaders}
        resp = self.session.post(deleteUrl, json=savejson, headers=headers, proxies=self.proxy)
        pass

    def upload_file(self, file, evidence=None, itemid=None, progressfunc=None, args=(), tokenize=False):
        try:
            fileurl = self.path + 'admin/tool/lp/user_evidence_edit.php?userid=' + self.userid
            resp = self.session.get(fileurl, proxies=self.proxy, headers=self.baseheaders)
            soup = BeautifulSoup(resp.text, 'html.parser')
            sesskey = self.sesskey
            if self.sesskey == '':
                sesskey = soup.find('input', attrs={'name': 'sesskey'})['value']
            _qf__user_files_form = 1
            query = self.extractQuery(soup.find('object', attrs={'type': 'text/html'})['data'])
            client_id = self.getclientid(resp.text)

            itempostid = query['itemid']
            if itemid:
                itempostid = itemid

            of = open(file, 'rb')
            b = uuid.uuid4().hex
            try:
                areamaxbyttes = query['areamaxbytes']
                if areamaxbyttes == '0':
                    areamaxbyttes = '-1'
            except:
                areamaxbyttes = '-1'
            upload_data = {
                'title': (None, ''),
                'author': (None, 'ObisoftDev'),
                'license': (None, 'allrightsreserved'),
                'itemid': (None, itempostid),
                'repo_id': (None, str(self.repo_id)),
                'p': (None, ''),
                'page': (None, ''),
                'env': (None, query['env']),
                'sesskey': (None, sesskey),
                'client_id': (None, client_id),
                'maxbytes': (None, query['maxbytes']),
                'areamaxbytes': (None, areamaxbyttes),
                'ctx_id': (None, query['ctx_id']),
                'savepath': (None, '/')}
            upload_file = {
                'repo_upload_file': (file, of, 'application/octet-stream'),
                **upload_data
            }
            post_file_url = self.path + 'repository/repository_ajax.php?action=upload'
            encoder = rt.MultipartEncoder(upload_file, boundary=b)
            progrescall = CallingUpload(progressfunc, file, args)
            callback = partial(progrescall)
            monitor = MultipartEncoderMonitor(encoder, callback=callback)
            resp2 = self.session.post(post_file_url, data=monitor,
                                      headers={"Content-Type": "multipart/form-data; boundary=" + b,
                                               **self.baseheaders}, proxies=self.proxy)
            of.close()

            # save evidence
            if evidence:
                evidence['files'] = itempostid

            data = self.parsejson(resp2.text)
            data['url'] = str(data['url']).replace('\\', '')
            data['normalurl'] = data['url']
            if self.userdata:
                if 'token' in self.userdata and not tokenize:
                    name = str(data['url']).split('/')[-1]
                    data['url'] = self.path + 'webservice/pluginfile.php/' + query['ctx_id'] + '/core_competency/userevidence/' + \
                                  evidence['id'] + '/' + name + '?token=' + self.userdata['token']
                if tokenize:
                    data['url'] = self.host_tokenize + S5Crypto.encrypt(data['url']) + '/' + self.userdata['s5token']
            return itempostid, data
        except:
            return None, None

    def upload_file_blog(self, file, blog=None, itemid=None, progressfunc=None, args=(), tokenize=False):
        try:
            fileurl = self.path + 'blog/edit.php?action=add&userid=' + self.userid
            resp = self.session.get(fileurl, proxies=self.proxy, headers=self.baseheaders)
            soup = BeautifulSoup(resp.text, 'html.parser')
            sesskey = self.sesskey
            if self.sesskey == '':
                sesskey = soup.find('input', attrs={'name': 'sesskey'})['value']
            _qf__user_files_form = 1
            query = self.extractQuery(soup.find('object', attrs={'type': 'text/html'})['data'])
            client_id = self.getclientid(resp.text)

            itempostid = query['itemid']
            if itemid:
                itempostid = itemid

            of = open(file, 'rb')
            b = uuid.uuid4().hex
            try:
                areamaxbyttes = query['areamaxbytes']
                if areamaxbyttes == '0':
                    areamaxbyttes = '-1'
            except:
                areamaxbyttes = '-1'
            upload_data = {
                'title': (None, ''),
                'author': (None, 'ObisoftDev'),
                'license': (None, 'allrightsreserved'),
                'itemid': (None, itempostid),
                'repo_id': (None, str(self.repo_id)),
                'p': (None, ''),
                'page': (None, ''),
                'env': (None, query['env']),
                'sesskey': (None, sesskey),
                'client_id': (None, client_id),
                'maxbytes': (None, query['maxbytes']),
                'areamaxbytes': (None, areamaxbyttes),
                'ctx_id': (None, query['ctx_id']),
                'savepath': (None, '/')}
            upload_file = {
                'repo_upload_file': (file, of, 'application/octet-stream'),
                **upload_data
            }
            post_file_url = self.path + 'repository/repository_ajax.php?action=upload'
            encoder = rt.MultipartEncoder(upload_file, boundary=b)
            progrescall = CallingUpload(progressfunc, file, args)
            callback = partial(progrescall)
            monitor = MultipartEncoderMonitor(encoder, callback=callback)
            resp2 = self.session.post(post_file_url, data=monitor,
                                      headers={"Content-Type": "multipart/form-data; boundary=" + b,
                                               **self.baseheaders}, proxies=self.proxy)
            of.close()

            data = self.parsejson(resp2.text)
            data['url'] = str(data['url']).replace('\\', '')
            data['normalurl'] = data['url']
            if self.userdata:
                if 'token' in self.userdata and not tokenize:
                    data['url'] = str(data['url']).replace('pluginfile.php/', 'webservice/pluginfile.php/') + '?token=' + \
                                  self.userdata['token']
                if tokenize:
                    data['url'] = self.host_tokenize + S5Crypto.encrypt(data['url']) + '/' + self.userdata['s5token']
            return itempostid, data
        except:
            return None, None

    def upload_file_perfil(self, file, progressfunc=None, args=(), tokenize=False):
        file_edit = f'{self.path}user/edit.php?id={self.userid}&returnto=profile'
        resp = self.session.get(file_edit, proxies=self.proxy, headers=self.baseheaders)
        soup = BeautifulSoup(resp.text, 'html.parser')
        sesskey = self.sesskey
        if self.sesskey == '':
            sesskey = soup.find('input', attrs={'name': 'sesskey'})['value']
        usertext = 'ObisoftDev'
        query = self.extractQuery(soup.find('object', attrs={'type': 'text/html'})['data'])
        client_id = str(soup.find('div', {'class': 'filemanager'})['id']).replace('filemanager-', '')

        upload_file = f'{self.path}repository/repository_ajax.php?action=upload'

        of = open(file, 'rb')
        b = uuid.uuid4().hex
        try:
            areamaxbyttes = query['areamaxbytes']
            if areamaxbyttes == '0':
                areamaxbyttes = '-1'
        except:
            areamaxbyttes = '-1'
        upload_data = {
            'title': (None, ''),
            'author': (None, 'ObisoftDev'),
            'license': (None, 'allrightsreserved'),
            'itemid': (None, query['itemid']),
            'repo_id': (None, str(self.repo_id)),
            'p': (None, ''),
            'page': (None, ''),
            'env': (None, query['env']),
            'sesskey': (None, sesskey),
            'client_id': (None, client_id),
            'maxbytes': (None, query['maxbytes']),
            'areamaxbytes': (None, areamaxbyttes),
            'ctx_id': (None, query['ctx_id']),
            'savepath': (None, '/')}
        upload_file = {
            'repo_upload_file': (file, of, 'application/octet-stream'),
            **upload_data
        }
        post_file_url = self.path + 'repository/repository_ajax.php?action=upload'
        encoder = rt.MultipartEncoder(upload_file, boundary=b)
        progrescall = CallingUpload(progressfunc, file, args)
        callback = partial(progrescall)
        monitor = MultipartEncoderMonitor(encoder, callback=callback)
        resp2 = self.session.post(post_file_url, data=monitor,
                                  headers={"Content-Type": "multipart/form-data; boundary=" + b, **self.baseheaders},
                                  proxies=self.proxy)
        of.close()

        data = self.parsejson(resp2.text)
        data['url'] = str(data['url']).replace('\\', '')
        data['normalurl'] = data['url']
        if self.userdata:
            if 'token' in self.userdata and not tokenize:
                data['url'] = str(data['url']).replace('pluginfile.php/', 'webservice/pluginfile.php/') + '?token=' + \
                              self.userdata['token']
            if tokenize:
                data['url'] = self.host_tokenize + S5Crypto.encrypt(data['url']) + '/' + self.userdata['s5token']

        payload = {
            'returnurl': file_edit,
            'sesskey': sesskey,
            '_qf__user_files_form': '.jpg',
            'submitbutton': 'Guardar+cambios'
        }
        resp3 = self.session.post(file_edit, data=payload, headers=self.baseheaders)

        return None, data

    def upload_file_draft(self, file, progressfunc=None, args=(), tokenize=False):
        file_edit = f'{self.path}user/files.php'
        resp = self.session.get(file_edit, proxies=self.proxy, headers=self.baseheaders)
        soup = BeautifulSoup(resp.text, 'html.parser')
        sesskey = self.sesskey
        if self.sesskey == '':
            sesskey = soup.find('input', attrs={'name': 'sesskey'})['value']
        usertext = 'ObisoftDev'
        query = self.extractQuery(soup.find('object', attrs={'type': 'text/html'})['data'])
        client_id = str(soup.find('div', {'class': 'filemanager'})['id']).replace('filemanager-', '')

        upload_file = f'{self.path}repository/repository_ajax.php?action=upload'

        of = open(file, 'rb')
        b = uuid.uuid4().hex
        areamaxbyttes = query['areamaxbytes']
        if areamaxbyttes == '0':
            areamaxbyttes = '-1'
        upload_data = {
            'title': (None, ''),
            'author': (None, 'ObisoftDev'),
            'license': (None, 'allrightsreserved'),
            'itemid': (None, query['itemid']),
            'repo_id': (None, str(self.repo_id)),
            'p': (None, ''),
            'page': (None, ''),
            'env': (None, query['env']),
            'sesskey': (None, sesskey),
            'client_id': (None, client_id),
            'maxbytes': (None, query['maxbytes']),
            'areamaxbytes': (None, areamaxbyttes),
            'ctx_id': (None, query['ctx_id']),
            'savepath': (None, '/')}
        upload_file = {
            'repo_upload_file': (file, of, 'application/octet-stream'),
            **upload_data
        }
        post_file_url = self.path + 'repository/repository_ajax.php?action=upload'
        encoder = rt.MultipartEncoder(upload_file, boundary=b)
        progrescall = CallingUpload(progressfunc, file, args)
        callback = partial(progrescall)
        monitor = MultipartEncoderMonitor(encoder, callback=callback)
        resp2 = self.session.post(post_file_url, data=monitor,
                                  headers={"Content-Type": "multipart/form-data; boundary=" + b, **self.baseheaders},
                                  proxies=self.proxy)
        of.close()

        data = self.parsejson(resp2.text)
        data['url'] = str(data['url']).replace('\\', '')
        data['normalurl'] = data['url']
        if self.userdata:
            if 'token' in self.userdata and not tokenize:
                data['url'] = str(data['url']).replace('pluginfile.php/', 'webservice/pluginfile.php/') + '?token=' + \
                              self.userdata['token']
            if tokenize:
                data['url'] = self.host_tokenize + S5Crypto.encrypt(data['url']) + '/' + self.userdata['s5token']
        return None, data

    def upload_file_calendar(self, file, progressfunc=None, args=(), tokenize=False):
        """
        Sube un archivo - el evento se creará automáticamente después
        """
        # Este método ahora es idéntico a upload_file_draft o upload_file_blog
        # porque el evento se crea en processUploadFiles
        return self.upload_file_draft(file, progressfunc, args, tokenize)

    def parsejson(self, json_str):
        data = {}
        tokens = str(json_str).replace('{', '').replace('}', '').split(',')
        for t in tokens:
            split = str(t).split(':', 1)
            data[str(split[0]).replace('"', '')] = str(split[1]).replace('"', '')
        return data

    def getclientid(self, html):
        index = str(html).index('client_id')
        max = 25
        ret = html[index:(index + max)]
        return str(ret).replace('client_id":"', '')

    def extractQuery(self, url):
        tokens = str(url).split('?')[1].split('&')
        retQuery = {}
        for q in tokens:
            qspl = q.split('=')
            try:
                retQuery[qspl[0]] = qspl[1]
            except:
                retQuery[qspl[0]] = None
        return retQuery

    def getFiles(self):
        urlfiles = self.path + 'user/files.php'
        resp = self.session.get(urlfiles, proxies=self.proxy, headers=self.baseheaders)
        soup = BeautifulSoup(resp.text, 'html.parser')
        sesskey = soup.find('input', attrs={'name': 'sesskey'})['value']
        client_id = self.getclientid(resp.text)
        filepath = '/'
        query = self.extractQuery(soup.find('object', attrs={'type': 'text/html'})['data'])
        payload = {'sesskey': sesskey, 'client_id': client_id, 'filepath': filepath, 'itemid': query['itemid']}
        postfiles = self.path + 'repository/draftfiles_ajax.php?action=list'
        resp = self.session.post(postfiles, data=payload, proxies=self.proxy, headers=self.baseheaders)
        dec = json.JSONDecoder()
        jsondec = dec.decode(resp.text)
        return jsondec['list']

    def delteFile(self, name):
        urlfiles = self.path + 'user/files.php'
        resp = self.session.get(urlfiles, proxies=self.proxy, headers=self.baseheaders)
        soup = BeautifulSoup(resp.text, 'html.parser')
        _qf__core_user_form_private_files = soup.find('input', {'name': '_qf__core_user_form_private_files'})['value']
        files_filemanager = soup.find('input', attrs={'name': 'files_filemanager'})['value']
        sesskey = soup.find('input', attrs={'name': 'sesskey'})['value']
        client_id = self.getclientid(resp.text)
        filepath = '/'
        query = self.extractQuery(soup.find('object', attrs={'type': 'text/html'})['data'])
        payload = {'sesskey': sesskey, 'client_id': client_id, 'filepath': filepath, 'itemid': query['itemid'],
                   'filename': name}
        postdelete = self.path + 'repository/draftfiles_ajax.php?action=delete'
        resp = self.session.post(postdelete, data=payload, proxies=self.proxy, headers=self.baseheaders)

        # save file
        saveUrl = self.path + 'lib/ajax/service.php?sesskey=' + sesskey + '&info=core_form_dynamic_form'
        savejson = [{"index": 0, "methodname": "core_form_dynamic_form",
                     "args": {"formdata": "sesskey=" + sesskey + "&_qf__core_user_form_private_files=" + _qf__core_user_form_private_files + "&files_filemanager=" + query[
                         'itemid'] + "", "form": "core_user\\form\\private_files"}}]
        headers = {'Content-type': 'application/json', 'Accept': 'application/json, text/javascript, */*; q=0.01',
                   **self.baseheaders}
        resp3 = self.session.post(saveUrl, json=savejson, headers=headers, proxies=self.proxy)

        return resp3

    def logout(self):
        logouturl = self.path + 'login/logout.php?sesskey=' + self.sesskey
        self.session.post(logouturl, proxies=self.proxy, headers=self.baseheaders)
