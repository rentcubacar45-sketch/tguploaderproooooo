from pyobigram.utils import sizeof_fmt, get_file_size, createID, nice_time
from pyobigram.client import ObigramClient, inlineQueryResultArticle
from MoodleClient import MoodleClient

from JDatabase import JsonDatabase
import zipfile
import os
import infos
import xdlink
import mediafire
import datetime
import time
import youtube
import NexCloudClient

from pydownloader.downloader import Downloader
from ProxyCloud import ProxyCloud
import ProxyCloud
import socket
import S5Crypto


def downloadFile(downloader, filename, currentBits, totalBits, speed, time, args):
    try:
        bot = args[0]
        message = args[1]
        thread = args[2]
        if thread.getStore('stop'):
            downloader.stop()
        downloadingInfo = infos.createDownloading(filename, totalBits, currentBits, speed, time, tid=thread.id)
        bot.editMessageText(message, downloadingInfo)
    except Exception as ex:
        print(str(ex))
    pass


def uploadFile(filename, currentBits, totalBits, speed, time, args):
    try:
        bot = args[0]
        message = args[1]
        originalfile = args[2]
        thread = args[3]
        downloadingInfo = infos.createUploading(filename, totalBits, currentBits, speed, time, originalfile)
        bot.editMessageText(message, downloadingInfo)
    except Exception as ex:
        print(str(ex))
    pass


def processUploadFiles(filename, filesize, files, update, bot, message, thread=None, jdb=None):
    try:
        bot.editMessageText(message, '🤜Preparando Para Subir☁...')
        evidence = None
        fileid = None
        user_info = jdb.get_user(update.message.sender.username)
        cloudtype = user_info['cloudtype']
        proxy = ProxyCloud.parse(user_info['proxy'])
        
        if cloudtype == 'moodle':
            client = MoodleClient(user_info['moodle_user'],
                                  user_info['moodle_password'],
                                  user_info['moodle_host'],
                                  user_info['moodle_repo_id'],
                                  proxy=proxy)
            loged = client.login()
            itererr = 0
            if loged:
                if user_info['uploadtype'] == 'evidence':
                    evidences = client.getEvidences()
                    evidname = str(filename).split('.')[0]
                    for evid in evidences:
                        if evid['name'] == evidname:
                            evidence = evid
                            break
                    if evidence is None:
                        evidence = client.createEvidence(evidname)

                originalfile = ''
                if len(files) > 1:
                    originalfile = filename
                
                draftlist = []
                uploaded_files = []  # 🔥 NUEVO: Lista para guardar info de archivos subidos
                
                for f in files:
                    f_size = get_file_size(f)
                    resp = None
                    iter = 0
                    tokenize = False
                    if user_info['tokenize'] != 0:
                       tokenize = True
                    
                    while resp is None:
                        if user_info['uploadtype'] == 'evidence':
                            fileid, resp = client.upload_file(f, evidence, fileid, progressfunc=uploadFile, args=(bot, message, originalfile, thread), tokenize=tokenize)
                            draftlist.append(resp)
                        
                        if user_info['uploadtype'] == 'draft':
                            fileid, resp = client.upload_file_draft(f, progressfunc=uploadFile, args=(bot, message, originalfile, thread), tokenize=tokenize)
                            draftlist.append(resp)
                        
                        if user_info['uploadtype'] == 'blog':
                            fileid, resp = client.upload_file_blog(f, progressfunc=uploadFile, args=(bot, message, originalfile, thread), tokenize=tokenize)
                            draftlist.append(resp)
                        
                        if user_info['uploadtype'] == 'calendario':
                            fileid, resp = client.upload_file_calendar(f, progressfunc=uploadFile, args=(bot, message, originalfile, thread), tokenize=tokenize)
                            draftlist.append(resp)
                        
                        iter += 1
                        if iter >= 10:
                            break
                    
                    if resp and 'url' in resp:
                        # 🔥 NUEVO: Guardar información del archivo subido
                        file_info = {
                            'name': os.path.basename(f),
                            'url': resp['url'],
                            'size': f_size
                        }
                        uploaded_files.append(file_info)
                        draftlist.append(resp)
                    
                    os.unlink(f)
                
                # 🔥 NUEVO: CREAR EVENTO ÚNICO PARA ARCHIVOS COMPRIMIDOS
                if uploaded_files and user_info['uploadtype'] in ['blog', 'calendario']:
                    try:
                        if len(uploaded_files) == 1:
                            # Un solo archivo: evento normal
                            file_info = uploaded_files[0]
                            event_data = client.createNewEvent({
                                'file': file_info['name'],
                                'url': file_info['url']
                            })
                            
                            # Actualizar URL en la respuesta con enlace formateado del evento
                            if event_data and len(event_data) > 0:
                                for draft in draftlist:
                                    if isinstance(draft, dict):
                                        draft['event_created'] = True
                                        try:
                                            if 'data' in event_data[0] and 'event' in event_data[0]['data']:
                                                event_info = event_data[0]['data']['event']
                                                draft['event_id'] = event_info.get('id', '')
                                        except:
                                            draft['event_id'] = ''
                        else:
                            # Múltiples archivos (partes comprimidas): evento con todos los enlaces
                            # Obtener nombre del archivo original (sin partes)
                            original_name = filename
                            
                            # Crear descripción con TODOS los enlaces
                            description = f'<p dir="ltr" style="text-align: left;">'
                            description += f'<strong>📦 Archivo comprimido en partes:</strong> {original_name}<br>'
                            description += f'<strong>📊 Total partes:</strong> {len(uploaded_files)}<br><br>'
                            description += f'<strong>🔗 Enlaces de descarga:</strong><br>'
                            
                            for i, file_info in enumerate(uploaded_files):
                                part_num = i + 1
                                description += f'{part_num}. <a href="{file_info["url"]}">{file_info["name"]}</a> ({sizeof_fmt(file_info["size"])})<br>'
                            
                            description += f'</p>'
                            
                            # Usar la primera URL como enlace principal
                            main_url = uploaded_files[0]['url']
                            
                            # Crear evento especial para múltiples partes
                            event_data = client.createNewEvent({
                                'file': f"{original_name} ({len(uploaded_files)} partes)",
                                'url': main_url,
                                'custom_description': description
                            })
                            
                            # Marcar todos los drafts con evento creado
                            if event_data and len(event_data) > 0:
                                for draft in draftlist:
                                    if isinstance(draft, dict):
                                        draft['event_created'] = True
                                        try:
                                            if 'data' in event_data[0] and 'event' in event_data[0]['data']:
                                                event_info = event_data[0]['data']['event']
                                                draft['event_id'] = event_info.get('id', '')
                                        except:
                                            draft['event_id'] = ''
                    except Exception as e:
                        print(f"Error creando evento: {str(e)}")
                
                if user_info['uploadtype'] == 'evidence':
                    try:
                        client.saveEvidence(evidence)
                    except:
                        pass
                return draftlist
            else:
                bot.editMessageText(message, '❌Error En La Pagina❌')
        elif cloudtype == 'cloud':
            tokenize = False
            if user_info['tokenize'] != 0:
               tokenize = True
            bot.editMessageText(message, '🤜Subiendo ☁ Espere Mientras... 😄')
            host = user_info['moodle_host']
            user = user_info['moodle_user']
            passw = user_info['moodle_password']
            remotepath = user_info['dir']
            client = NexCloudClient.NexCloudClient(user, passw, host, proxy=proxy)
            loged = client.login()
            if loged:
               originalfile = ''
               if len(files) > 1:
                    originalfile = filename
               filesdata = []
               for f in files:
                   data = client.upload_file(f, path=remotepath, progressfunc=uploadFile, args=(bot, message, originalfile, thread), tokenize=tokenize)
                   filesdata.append(data)
                   os.unlink(f)
               return filesdata
        return None
    except Exception as ex:
        bot.editMessageText(message, '❌Error❌\n' + str(ex))
        return None


def processFile(update, bot, message, file, thread=None, jdb=None):
    file_size = get_file_size(file)
    getUser = jdb.get_user(update.message.sender.username)
    max_file_size = 1024 * 1024 * getUser['zips']
    file_upload_count = 0
    client = None
    findex = 0
    if file_size > max_file_size:
        compresingInfo = infos.createCompresing(file, file_size, max_file_size)
        bot.editMessageText(message, compresingInfo)
        zipname = str(file).split('.')[0] + createID()
        mult_file = zipfile.MultiFile(zipname, max_file_size)
        zip = zipfile.ZipFile(mult_file, mode='w', compression=zipfile.ZIP_DEFLATED)
        zip.write(file)
        zip.close()
        mult_file.close()
        client = processUploadFiles(file, file_size, mult_file.files, update, bot, message, jdb=jdb)
        try:
            os.unlink(file)
        except:
            pass
        file_upload_count = len(mult_file.files)
    else:
        client = processUploadFiles(file, file_size, [file], update, bot, message, jdb=jdb)
        file_upload_count = 1
    bot.editMessageText(message, '🤜Preparando Archivo📄...')
    evidname = ''
    files = []
    if client:
        if getUser['cloudtype'] == 'moodle':
            if getUser['uploadtype'] == 'evidence':
                try:
                    evidname = str(file).split('.')[0]
                    txtname = evidname + '.txt'
                    evidences = client.getEvidences()
                    for ev in evidences:
                        if ev['name'] == evidname:
                           files = ev['files']
                           break
                        if len(ev['files']) > 0:
                           findex += 1
                    client.logout()
                except:
                    pass
            if getUser['uploadtype'] == 'draft' or getUser['uploadtype'] == 'blog' or getUser['uploadtype'] == 'calendario':
               for draft in client:
                   files.append({'name': draft['file'], 'directurl': draft['url']})
                   
                   # 🔥 NUEVO: Mostrar información del evento si se creó
                   if 'event_created' in draft and draft['event_created']:
                       event_info = f"\n📅 **Evento creado en calendario**"
                       if draft.get('event_id'):
                           event_info += f" (ID: {draft['event_id']})"
                       bot.sendMessage(message.chat.id, event_info)
        else:
            for data in client:
                files.append({'name': data['name'], 'directurl': data['url']})
        bot.deleteMessage(message.chat.id, message.message_id)
        finishInfo = infos.createFinishUploading(file, file_size, max_file_size, file_upload_count, file_upload_count, findex)
        filesInfo = infos.createFileMsg(file, files)
        bot.sendMessage(message.chat.id, finishInfo + '\n' + filesInfo, parse_mode='html')
        if len(files) > 0:
            txtname = str(file).split('/')[-1].split('.')[0] + '.txt'
            sendTxt(txtname, files, update, bot)


def ddl(update, bot, message, url, file_name='', thread=None, jdb=None):
    downloader = Downloader()
    file = downloader.download_url(url, progressfunc=downloadFile, args=(bot, message, thread))
    if not downloader.stoping:
        if file:
            processFile(update, bot, message, file, jdb=jdb)
        else:
            bot.editMessageText(message, '❌Error en la descarga❌')


def sendTxt(name, files, update, bot):
    txt = open(name, 'w')
    fi = 0
    for f in files:
        separator = ''
        if fi < len(files) - 1:
            separator += '\n'
        txt.write(f['directurl'] + separator)
        fi += 1
    txt.close()
    bot.sendFile(update.message.chat.id, name)
    os.unlink(name)


def onmessage(update, bot: ObigramClient):
    try:
        thread = bot.this_thread
        username = update.message.sender.username
        
        # CONFIGURACIÓN MANUAL DEL ADMINISTRADOR
        tl_admin_user = 'Eliel_21'

        jdb = JsonDatabase('database')
        jdb.check_create()
        jdb.load()

        user_info = jdb.get_user(username)

        if username == tl_admin_user or tl_admin_user == 'Eliel_21' or user_info:
            if user_info is None:
                if username == tl_admin_user:
                    jdb.create_admin(username)
                else:
                    jdb.create_user(username)
                user_info = jdb.get_user(username)
                jdb.save()
        else:
            return

        msgText = ''
        try:
            msgText = update.message.text
        except:
            pass

        # comandos de admin
        if '/adduser' in msgText:
            isadmin = jdb.is_admin(username)
            if isadmin:
                try:
                    user = str(msgText).split(' ')[1]
                    jdb.create_user(user)
                    jdb.save()
                    msg = '😃Genial @' + user + ' ahora tiene acceso al bot👍'
                    bot.sendMessage(update.message.chat.id, msg)
                except:
                    bot.sendMessage(update.message.chat.id, '❌Error en el comando /adduser username❌')
            else:
                bot.sendMessage(update.message.chat.id, '❌No Tiene Permiso❌')
            return
        if '/banuser' in msgText:
            isadmin = jdb.is_admin(username)
            if isadmin:
                try:
                    user = str(msgText).split(' ')[1]
                    if user == username:
                        bot.sendMessage(update.message.chat.id, '❌No Se Puede Banear Usted❌')
                        return
                    jdb.remove(user)
                    jdb.save()
                    msg = '🦶Fuera @' + user + ' Baneado❌'
                    bot.sendMessage(update.message.chat.id, msg)
                except:
                    bot.sendMessage(update.message.chat.id, '❌Error en el comando /banuser username❌')
            else:
                bot.sendMessage(update.message.chat.id, '❌No Tiene Permiso❌')
            return
        if '/getdb' in msgText:
            isadmin = jdb.is_admin(username)
            if isadmin:
                bot.sendMessage(update.message.chat.id, 'Base De Datos👇')
                bot.sendFile(update.message.chat.id, 'database.jdb')
            else:
                bot.sendMessage(update.message.chat.id, '❌No Tiene Permiso❌')
            return
        # end

        # comandos de usuario
        if '/tutorial' in msgText:
            tuto = open('tuto.txt', 'r')
            bot.sendMessage(update.message.chat.id, tuto.read())
            tuto.close()
            return
        if '/myuser' in msgText:
            getUser = user_info
            if getUser:
                statInfo = infos.createStat(username, getUser, jdb.is_admin(username))
                bot.sendMessage(update.message.chat.id, statInfo)
                return
        if '/zips' in msgText:
            getUser = user_info
            if getUser:
                try:
                   size = int(str(msgText).split(' ')[1])
                   getUser['zips'] = size
                   jdb.save_data_user(username, getUser)
                   jdb.save()
                   msg = '😃Genial los zips seran de ' + sizeof_fmt(size * 1024 * 1024) + ' las partes👍'
                   bot.sendMessage(update.message.chat.id, msg)
                except:
                   bot.sendMessage(update.message.chat.id, '❌Error en el comando /zips size❌')
                return
        if '/account' in msgText:
            try:
                account = str(msgText).split(' ', 2)[1].split(',')
                user = account[0]
                passw = account[1]
                getUser = user_info
                if getUser:
                    getUser['moodle_user'] = user
                    getUser['moodle_password'] = passw
                    jdb.save_data_user(username, getUser)
                    jdb.save()
                    statInfo = infos.createStat(username, getUser, jdb.is_admin(username))
                    bot.sendMessage(update.message.chat.id, statInfo)
            except:
                bot.sendMessage(update.message.chat.id, '❌Error en el comando /account user,password❌')
            return
        if '/host' in msgText:
            try:
                cmd = str(msgText).split(' ', 2)
                host = cmd[1]
                getUser = user_info
                if getUser:
                    getUser['moodle_host'] = host
                    jdb.save_data_user(username, getUser)
                    jdb.save()
                    statInfo = infos.createStat(username, getUser, jdb.is_admin(username))
                    bot.sendMessage(update.message.chat.id, statInfo)
            except:
                bot.sendMessage(update.message.chat.id, '❌Error en el comando /host moodlehost❌')
            return
        if '/repoid' in msgText:
            try:
                cmd = str(msgText).split(' ', 2)
                repoid = int(cmd[1])
                getUser = user_info
                if getUser:
                    getUser['moodle_repo_id'] = repoid
                    jdb.save_data_user(username, getUser)
                    jdb.save()
                    statInfo = infos.createStat(username, getUser, jdb.is_admin(username))
                    bot.sendMessage(update.message.chat.id, statInfo)
            except:
                bot.sendMessage(update.message.chat.id, '❌Error en el comando /repo id❌')
            return
        if '/tokenize_on' in msgText:
            try:
                getUser = user_info
                if getUser:
                    getUser['tokenize'] = 1
                    jdb.save_data_user(username, getUser)
                    jdb.save()
                    statInfo = infos.createStat(username, getUser, jdb.is_admin(username))
                    bot.sendMessage(update.message.chat.id, statInfo)
            except:
                bot.sendMessage(update.message.chat.id, '❌Error en el comando /tokenize state❌')
            return
        if '/tokenize_off' in msgText:
            try:
                getUser = user_info
                if getUser:
                    getUser['tokenize'] = 0
                    jdb.save_data_user(username, getUser)
                    jdb.save()
                    statInfo = infos.createStat(username, getUser, jdb.is_admin(username))
                    bot.sendMessage(update.message.chat.id, statInfo)
            except:
                bot.sendMessage(update.message.chat.id, '❌Error en el comando /tokenize state❌')
            return
        if '/cloud' in msgText:
            try:
                cmd = str(msgText).split(' ', 2)
                repoid = cmd[1]
                getUser = user_info
                if getUser:
                    getUser['cloudtype'] = repoid
                    jdb.save_data_user(username, getUser)
                    jdb.save()
                    statInfo = infos.createStat(username, getUser, jdb.is_admin(username))
                    bot.sendMessage(update.message.chat.id, statInfo)
            except:
                bot.sendMessage(update.message.chat.id, '❌Error en el comando /cloud (moodle or cloud)❌')
            return
        if '/uptype' in msgText:
            try:
                cmd = str(msgText).split(' ', 2)
                type = cmd[1]
                getUser = user_info
                if getUser:
                    getUser['uploadtype'] = type
                    jdb.save_data_user(username, getUser)
                    jdb.save()
                    statInfo = infos.createStat(username, getUser, jdb.is_admin(username))
                    bot.sendMessage(update.message.chat.id, statInfo)
            except:
                bot.sendMessage(update.message.chat.id, '❌Error en el comando /uptype (typo de subida (evidence,draft,blog,calendario))❌')
            return
        if '/proxy' in msgText:
            try:
                cmd = str(msgText).split(' ', 2)
                proxy = cmd[1]
                getUser = user_info
                if getUser:
                    getUser['proxy'] = proxy
                    jdb.save_data_user(username, getUser)
                    jdb.save()
                    statInfo = infos.createStat(username, getUser, jdb.is_admin(username))
                    bot.sendMessage(update.message.chat.id, statInfo)
            except:
                if user_info:
                    user_info['proxy'] = ''
                    statInfo = infos.createStat(username, user_info, jdb.is_admin(username))
                    bot.sendMessage(update.message.chat.id, statInfo)
            return
        if '/dir' in msgText:
            try:
                cmd = str(msgText).split(' ', 2)
                repoid = cmd[1]
                getUser = user_info
                if getUser:
                    getUser['dir'] = repoid + '/'
                    jdb.save_data_user(username, getUser)
                    jdb.save()
                    statInfo = infos.createStat(username, getUser, jdb.is_admin(username))
                    bot.sendMessage(update.message.chat.id, statInfo)
            except:
                bot.sendMessage(update.message.chat.id, '❌Error en el comando /dir folder❌')
            return
        if '/cancel_' in msgText:
            try:
                cmd = str(msgText).split('_', 2)
                tid = cmd[1]
                tcancel = bot.threads[tid]
                msg = tcancel.getStore('msg')
                tcancel.store('stop', True)
                time.sleep(3)
                bot.editMessageText(msg, '❌Tarea Cancelada❌')
            except Exception as ex:
                print(str(ex))
            return
        # end

        message = bot.sendMessage(update.message.chat.id, '🕰Procesando🕰...')

        thread.store('msg', message)

        if '/start' in msgText:
            start_msg = 'Bot          : TGUploaderPro v7.0 Fixed\n'
            start_msg += 'Desarrollador: @obisoftdevel\n'
            start_msg += 'Api          : https://github.com/ObisoftDev/tguploaderpro\n'
            start_msg += 'Uso          :Envia Enlaces De Descarga y Archivos Para Procesar (Configure Antes De Empezar , Vea El /tutorial)\n'
            bot.editMessageText(message, start_msg)
        elif '/files' == msgText and user_info['cloudtype'] == 'moodle':
             proxy = ProxyCloud.parse(user_info['proxy'])
             client = MoodleClient(user_info['moodle_user'],
                                   user_info['moodle_password'],
                                   user_info['moodle_host'],
                                   user_info['moodle_repo_id'], proxy=proxy)
             loged = client.login()
             if loged:
                 files = client.getEvidences()
                 filesInfo = infos.createFilesMsg(files)
                 bot.editMessageText(message, filesInfo)
                 client.logout()
             else:
                bot.editMessageText(message, '❌Error y Causas🧐\n1-Revise su Cuenta\n2-Servidor Desabilitado: ' + client.path)
        elif '/txt_' in msgText and user_info['cloudtype'] == 'moodle':
             findex = str(msgText).split('_')[1]
             findex = int(findex)
             proxy = ProxyCloud.parse(user_info['proxy'])
             client = MoodleClient(user_info['moodle_user'],
                                   user_info['moodle_password'],
                                   user_info['moodle_host'],
                                   user_info['moodle_repo_id'], proxy=proxy)
             loged = client.login()
             if loged:
                 evidences = client.getEvidences()
                 evindex = evidences[findex]
                 txtname = evindex['name'] + '.txt'
                 sendTxt(txtname, evindex['files'], update, bot)
                 client.logout()
                 bot.editMessageText(message, 'TxT Aqui👇')
             else:
                bot.editMessageText(message, '❌Error y Causas🧐\n1-Revise su Cuenta\n2-Servidor Desabilitado: ' + client.path)
             pass
        elif '/del_' in msgText and user_info['cloudtype'] == 'moodle':
            findex = int(str(msgText).split('_')[1])
            proxy = ProxyCloud.parse(user_info['proxy'])
            client = MoodleClient(user_info['moodle_user'],
                                   user_info['moodle_password'],
                                   user_info['moodle_host'],
                                   user_info['moodle_repo_id'],
                                   proxy=proxy)
            loged = client.login()
            if loged:
                evfile = client.getEvidences()[findex]
                client.deleteEvidence(evfile)
                client.logout()
                bot.editMessageText(message, 'Archivo Borrado 🦶')
            else:
                bot.editMessageText(message, '❌Error y Causas🧐\n1-Revise su Cuenta\n2-Servidor Desabilitado: ' + client.path)
        elif '/delall' in msgText and user_info['cloudtype'] == 'moodle':
            proxy = ProxyCloud.parse(user_info['proxy'])
            client = MoodleClient(user_info['moodle_user'],
                                   user_info['moodle_password'],
                                   user_info['moodle_host'],
                                   user_info['moodle_repo_id'],
                                   proxy=proxy)
            loged = client.login()
            if loged:
                evfiles = client.getEvidences()
                for item in evfiles:
                    client.deleteEvidence(item)
                client.logout()
                bot.editMessageText(message, 'Archivo Borrado 🦶')
            else:
                bot.editMessageText(message, '❌Error y Causas🧐\n1-Revise su Cuenta\n2-Servidor Desabilitado: ' + client.path)       
        elif 'http' in msgText:
            url = msgText
            ddl(update, bot, message, url, file_name='', thread=thread, jdb=jdb)
        else:
            bot.editMessageText(message, '😵No se pudo procesar😵')
    except Exception as ex:
           print(str(ex))


def main():
    # CONFIGURACIÓN MANUAL DEL TOKEN DEL BOT
    bot_token = '8483127134:AAEHoM1qo8bwzY5MCkLlxGoHEN3H0Y6kkPM'

    bot = ObigramClient(bot_token)
    bot.onMessage(onmessage)
    bot.run()

if __name__ == '__main__':
    try:
        main()
    except:
        main()
