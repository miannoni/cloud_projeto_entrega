from factorizing1 import *

plataforma_ohio = platform("matteo", "us-east-2")

plataforma_ohio.initialize_platform()

plataforma_ohio.deleta_coisas_autoscale()

plataforma_ohio.deleta_minhas_instancias_existentes()

plataforma_ohio.cria_key_pair()

plataforma_ohio.cria_security_group("database")

plataforma_ohio.cria_instancia(type="database")

plataforma_ohio.cria_security_group("database_webserver")

plataforma_ohio.cria_instancia(type="database_webserver", ip_redirecionar=plataforma_ohio.instances_ip[0])

plataforma_ohio.set_ingress_no_security_group("database", permissions=[{"port": 27017, "ip": plataforma_ohio.instances_ip[1] + "/32"}])

plataforma = platform("matteo", "us-east-1")

plataforma.initialize_platform()

plataforma.deleta_coisas_autoscale()

plataforma.deleta_minhas_instancias_existentes()

plataforma.cria_key_pair()

plataforma.cria_security_group("NorthVirginia")

plataforma.cria_instancia(type="gateway", ip_redirecionar=plataforma_ohio.instances_ip[1])

plataforma_ohio.set_ingress_no_security_group("database_webserver", permissions=[{"port": 5000, "ip": plataforma.instances_ip[0] + "/32"}])

plataforma.set_ingress_no_security_group("NorthVirginia", permissions=[{"port": 5000, "ip": "0.0.0.0/0"}, {"port": 80, "ip": "0.0.0.0/0"}, {"port": 22, "ip": "0.0.0.0/0"}])

lb_dns = plataforma.dirty_load_balencer()

plataforma.dirty_auto_scaling()

print("O endereco da sua plataforma é:")
print("http://" + lb_dns)








































pass
