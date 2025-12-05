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
        if not text or '://' not in str(text):
            return None
        
        tokens = str(text).split('://')
        proxy_type = tokens[0].lower()
        
        # Validar tipo de proxy
        if proxy_type not in ['socks5', 'socks4', 'http', 'https']:
            return None
        
        proxy_address = tokens[1]
        
        # PRIMERO: Intentar como proxy ENCRIPTADO (para mantener compatibilidad)
        try:
            decrypted = S5Crypto.decrypt(str(proxy_address))
            if ':' in decrypted:
                proxy_tokens = decrypted.split(':')
                ip = proxy_tokens[0]
                
                # Manejar IPv6
                if len(proxy_tokens) > 2:
                    ip = ':'.join(proxy_tokens[:-1])
                    port_str = proxy_tokens[-1]
                else:
                    port_str = proxy_tokens[1]
                
                port = int(port_str)
                return ProxyCloud(ip, port, proxy_type)
        except:
            # Si falla la desencriptación, continuar...
            pass
        
        # SEGUNDO: Intentar como proxy NORMAL
        try:
            # Manejar formato IPv6: [2001:db8::1]:8080
            if ']:' in proxy_address:
                ip_end = proxy_address.rfind(']:')
                ip = proxy_address[:ip_end+1]
                port_str = proxy_address[ip_end+2:]
            elif ':' in proxy_address:
                parts = proxy_address.rsplit(':', 1)
                ip = parts[0]
                port_str = parts[1]
            else:
                return None
            
            port = int(port_str)
            return ProxyCloud(ip, port, proxy_type)
            
        except (ValueError, IndexError):
            return None
            
    except Exception:
        return None
