class ProxyCloud(object):
    def __init__(self, ip, port, type='socks5'):
        self.ip = ip
        self.port = port
        self.default = None
        self.type = type
    
    def set_default(self, socket):
        self.default = socket
    
    def as_dict_proxy(self):
        return {
            'http': f'{self.type}://{self.ip}:{self.port}',
            'https': f'{self.type}://{self.ip}:{self.port}'
        }

import S5Crypto

def parse(text):
    try:
        if not text:
            return None
        
        text = str(text).strip()
        
        # Verificar formato básico
        if '://' not in text:
            return None
        
        # Separar tipo y dirección
        tokens = text.split('://')
        proxy_type = tokens[0].lower()
        
        # Tipos válidos de proxy
        valid_types = ['socks5', 'socks4', 'http', 'https']
        if proxy_type not in valid_types:
            return None
        
        proxy_address = tokens[1]
        
        # INTENTAR PRIMERO COMO PROXY NORMAL (NO ENCRIPTADO)
        try:
            # Manejar diferentes formatos:
            # 1. IPv6: [2001:db8::1]:8080
            # 2. IPv4/hostname: 1.2.3.4:8080 o ejemplo.com:8080
            
            if ']:' in proxy_address:  # IPv6 con corchetes
                ip_end = proxy_address.rfind(']:')
                ip = proxy_address[:ip_end+1]
                port_str = proxy_address[ip_end+2:]
            elif ':' in proxy_address:  # IPv4 o hostname
                parts = proxy_address.rsplit(':', 1)
                ip = parts[0]
                port_str = parts[1]
            else:
                raise ValueError("Formato inválido")
            
            port = int(port_str)
            if 1 <= port <= 65535:
                return ProxyCloud(ip, port, proxy_type)
                
        except (ValueError, IndexError):
            # Si falla como proxy normal, continuar...
            pass
        
        # INTENTAR COMO PROXY ENCRIPTADO
        try:
            decrypted = S5Crypto.decrypt(str(proxy_address))
            
            if ':' in decrypted:
                proxy_tokens = decrypted.split(':')
                
                # Manejar IPv6 en formato encriptado
                if len(proxy_tokens) > 2:
                    ip = ':'.join(proxy_tokens[:-1])
                    port_str = proxy_tokens[-1]
                else:
                    ip = proxy_tokens[0]
                    port_str = proxy_tokens[1]
                
                port = int(port_str)
                if 1 <= port <= 65535:
                    return ProxyCloud(ip, port, proxy_type)
                    
        except:
            pass
            
    except:
        pass
    
    return None
