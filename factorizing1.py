from time import sleep
import os
import boto3
from botocore.exceptions import ClientError

class platform():
    def __init__(self, meu_nome, regiao):
        self.seu_nome = meu_nome
        self.regiao = regiao
        self.nome_chave = meu_nome + "_" + regiao + '_chaves'
        self.ec2 = None
        self.ec2R = None
        self.elb = None
        self.asg = None
        self.ec2_ohio = None
        self.vpc_id = None
        self.elbArn = None
        self.gatewayIP = None
        self.instances_ip = []
        self.custom_filter = []
        self.security_group_id = ""
        self.target_group_arns = []
        self.vpczones = []

    def initialize_platform(self):
        print("Initializing...")
        print()
        print("Name: %s" % self.seu_nome)
        print("KeyName will be: %s" % self.nome_chave)
        print()

        self.ec2 = boto3.client('ec2', region_name=self.regiao)
        self.ec2R = boto3.resource('ec2', region_name=self.regiao)
        self.elb = boto3.client('elbv2', region_name=self.regiao)
        self.asg = boto3.client('autoscaling', region_name=self.regiao)

    def deleta_coisas_autoscale(self):
        print("\nChecking autoscaling group conflicts...")
        response = self.asg.describe_auto_scaling_groups()
        for lconfig in response['AutoScalingGroups']:
            if lconfig['AutoScalingGroupName'] == 'asg-' + self.seu_nome:
                print("Conflict found, deleting autoscaling group...")
                response = self.asg.delete_auto_scaling_group(AutoScalingGroupName='asg-' + self.seu_nome, ForceDelete=True)

        print("\nChecking for load balencer conflicts...")
        response = self.elb.describe_load_balancers()
        for elb in response['LoadBalancers']:
            if (elb['LoadBalancerName'] == 'elb-' + self.seu_nome):
                print("Conflict found, deleting load balencer...")
                self.elb.delete_load_balancer(LoadBalancerArn=elb['LoadBalancerArn'])

        while True:
            try:
                response = self.elb.describe_load_balancers(Names=['elb-' + self.seu_nome])
            except:
                break

        print("\nChecking target group conflicts...")
        response = self.elb.describe_target_groups()
        for elb in response['TargetGroups']:
            if ((elb['TargetGroupName'] == 'target-a-' + self.seu_nome) or (elb['TargetGroupName'] == 'target-b-' + self.seu_nome)):
                print("Conflict found, resolving...")
                while True:
                    try:
                        self.elb.delete_target_group(TargetGroupArn=elb['TargetGroupArn'])
                        break
                    except:
                        print("Something went wrong deleting the target group, load balencer probably still being deleted...")
                        sleep(5)
                        print("Trying again")
                        continue

        print("\nChecking launch configuration conflicts...")
        response = self.asg.describe_launch_configurations()
        for lconfig in response['LaunchConfigurations']:
            if lconfig['LaunchConfigurationName'] == 'launch-config' + self.seu_nome:
                print("Conflict found, resolving...")
                self.asg.delete_launch_configuration(LaunchConfigurationName='launch-config' + self.seu_nome)

        print("\nChecking network interfaces dependencies...")
        response = self.ec2.describe_network_interfaces()
        deleto = False
        for lconfig in response['NetworkInterfaces']:
            if deleto == False:
                for group in lconfig['Groups']:
                    if group['GroupId'] == self.security_group_id:
                        print("Impairing dependency found, fixing dependencies...")
                        self.asg.delete_network_interfaces(NetworkInterfaceId=lconfig['NetworkInterfaceId'])
                        deleto = True

    def deleta_minhas_instancias_existentes(self):
        print("\nChecking for instance conflicts...")

        self.custom_filter = [{
            'Name':'tag:Owner',
            'Values': [self.seu_nome]}]

        response = self.ec2.describe_instances(Filters=self.custom_filter)
        instancias = []

        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instancias.append(instance['InstanceId'])

        if len(instancias) > 0:

            self.ec2.terminate_instances(InstanceIds = instancias)

            for instancia in instancias:
                instance = self.ec2R.Instance(instancia)

                if (instance.state['Name'] != 'terminated'):
                    print("Conflict found, resolving...")

                    while instance.state['Name'] != 'terminated':
                        print(instance.instance_id + " is " + instance.state['Name'])
                        self.ec2.terminate_instances(InstanceIds = [instancia])
                        sleep(5)
                        instance.load()

                    print("instance " + instance.instance_id + " state is now " + instance.state['Name'])

            print("No conflicts exist, continuing...")

    def cria_key_pair(self):
        print("\nCreating Key Pair")
        # CRIAR A KEY PAIR
        response = self.ec2.describe_key_pairs()

        # Se existe, deleta
        if (self.nome_chave in [x['KeyName'] for x in response['KeyPairs']]):
            print("Same name key found, deleting key with same name...")
            response = self.ec2.delete_key_pair(KeyName=self.nome_chave)

        # Cria
        response = self.ec2.create_key_pair(KeyName=self.nome_chave)
        print("KeyPair created, check your aws dashboard...")
        # print(response['KeyMaterial'])

        try:
            print("Writing keys to file %s" % (self.nome_chave + ".pem"))
            f = open(self.nome_chave + ".pem", "w")
        except:
            print("Permission to write new file denied, overriding permission and overwriting existing file...")
            os.chmod("./"+ self.nome_chave + ".pem", 0o777)
            f = open(self.nome_chave + ".pem", "w")

        f.write(response['KeyMaterial'])
        f.close()
        os.chmod("./"+ self.nome_chave + ".pem", 0o700)

    def cria_security_group(self, nome):
        print("\nCreating security group...")

        response = self.ec2.describe_vpcs()
        self.vpc_id = response.get('Vpcs', [{}])[0].get('VpcId', '')
        nome_do_grupo = self.seu_nome + '_security_group_' + nome

        while True:
            try:
                response = self.ec2.describe_security_groups()

                # Se existe, deleta
                for group in response['SecurityGroups']:

                    if (nome_do_grupo == group['GroupName']):
                        print("Same name security group found, deleting security group...")
                        response = self.ec2.delete_security_group(GroupId=group['GroupId'])

                print("Criating security group...")
                # Cria
                response = self.ec2.create_security_group(GroupName=nome_do_grupo,
                                                     Description='SG para a APS de ' + self.seu_nome,
                                                     VpcId=self.vpc_id)

                id_grupo = response['GroupId']
                self.security_group_id = id_grupo

                print('Security Group Created %s in vpc %s.' % (self.security_group_id, self.vpc_id))

                break
            except ClientError as e:
                print(e)
                print("Something went wrong, trying again...")
                continue

    def set_ingress_no_security_group(self, group_nome, permissions=None):
        print("\nSetting security group ingresses...")
        response = self.ec2.describe_security_groups()

        # Se existe, deleta
        nome_do_grupo = self.seu_nome + '_security_group_' + group_nome
        group_id = ""

        for group in response['SecurityGroups']:

            if (nome_do_grupo == group['GroupName']):
                print("Security group found, got group ID...")
                group_id = group['GroupId']

        print('Security group ingress starting...')
        listinha = []

        for perm in permissions:
            listinha.append(
            {'IpProtocol': 'tcp',
             'FromPort': perm["port"],
             'ToPort': perm["port"],
             'IpRanges': [{'CidrIp': perm["ip"]}]}
             )

        data = self.ec2.authorize_security_group_ingress(
            # GroupId=group_id,
            GroupName=nome_do_grupo,
            IpPermissions=listinha)
        # print(str(data))
        print('Ingress Successfully Set')

# TEM 1 SECURITY GROUP
    def cria_instancia(self, type = None, ip_redirecionar = None):
        print("\nCreating instance")

        if (type == None):
            arquivo = open("./initialize_instance.sh").read()
            nome_instancia = self.seu_nome + "_instancia"

        elif (type == "database"):
            arquivo = open("./initialize_instance_" + type + ".sh").read()
            nome_instancia = self.seu_nome + "_" + type

        elif (type == "database_webserver"):
            arquivo = open("./initialize_instance_" + type + ".sh").read()
            arquivo = arquivo[:arquivo.find('\n')] + '\nexport REDIRECTIP="' + ip_redirecionar + '"' + arquivo[arquivo.find('\n'):]
            nome_instancia = self.seu_nome + "_" + type

        else:
            arquivo = open("./initialize_instance_" + type + ".sh").read()
            arquivo = arquivo[:arquivo.find('\n')] + '\nexport REDIRECTIP="http://' + ip_redirecionar + ':5000"' + arquivo[arquivo.find('\n'):]
            nome_instancia = self.seu_nome + "_" + type

        if (self.regiao == "us-east-1"):
            instancias = self.ec2.run_instances(ImageId='ami-04b9e92b5572fa0d1', UserData = arquivo, TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key' : 'Owner', 'Value' : self.seu_nome}, {'Key': 'Name', 'Value': nome_instancia}]}], KeyName=self.nome_chave, SecurityGroupIds=[self.security_group_id], InstanceType="t2.micro", MinCount=1, MaxCount=1)
        else:
            instancias = self.ec2.run_instances(ImageId='ami-0d5d9d301c853a04a', UserData = arquivo, TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key' : 'Owner', 'Value' : self.seu_nome}, {'Key': 'Name', 'Value': nome_instancia}]}], KeyName=self.nome_chave, SecurityGroupIds=[self.security_group_id], InstanceType="t2.micro", MinCount=1, MaxCount=1)

        response = self.ec2.describe_instances(Filters=self.custom_filter)
        instancias = []
        dns_name = ""

        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instancias.append(instance['InstanceId'])

        if len(instancias) > 0:

            for instancia in instancias:
                instance = self.ec2R.Instance(instancia)

                if (instance.state['Name'] == 'pending'):
                    while instance.state['Name'] != 'running':
                        print("Instance pending, waiting to enter running state...")
                        sleep(5)
                        instance.load()
                    dns_name = instance.public_ip_address

        print("Instance running")

        if (dns_name not in self.instances_ip):
            self.instances_ip.append(dns_name)

#TEM 1 SECURITY GROUP
    def dirty_load_balencer(self):
        print("\nCreating Load Balencer...")

        subnet_ids = []

        response = self.ec2.describe_subnets()

        for subnet in response['Subnets']:
            subnet_ids.append(subnet['SubnetId'])

        self.vpczones = subnet_ids

        response = self.elb.create_load_balancer(Name="elb-" + self.seu_nome, SecurityGroups=[self.security_group_id], Subnets=subnet_ids)

        elbArn = response['LoadBalancers'][0]['LoadBalancerArn']
        dns_publico = response['LoadBalancers'][0]['DNSName']
        f = open("./export_dns.sh", "w")
        f.write("#!/bin/bash\nexport WEBSERVERIP=http://"+dns_publico)
        f.close()
        os.chmod("./export_dns.sh", 0o777)

        print("Load balencer creation done...")

        print("Creating Load Balencer target groups...")
        self.elbArn = elbArn

        response = self.elb.create_target_group(Name = 'target-a-' + self.seu_nome, Protocol='HTTP',  Port=5000, VpcId=self.vpc_id)

        tgg_a_Arn = response['TargetGroups'][0]['TargetGroupArn']

        response = self.elb.create_target_group(Name = 'target-b-' + self.seu_nome, Protocol='HTTP',  Port=5000, VpcId=self.vpc_id)

        tgg_b_Arn = response['TargetGroups'][0]['TargetGroupArn']

        self.target_group_arns = [tgg_a_Arn, tgg_b_Arn]

        print("Target groups done...")

        print("Creating listeners...")

        response = self.elb.create_listener(
            DefaultActions=[
                {
                    # 'TargetGroupArn': tgg_a_Arn,
                    'Type': 'forward',
                    "ForwardConfig": {
                        "TargetGroups": [
                            {
                                "TargetGroupArn": tgg_a_Arn,#"arn:aws:elasticloadbalancing:us-west-2:123456789012:targetgroup/blue-targets/73e2d6bc24d8a067",
                                "Weight": 10
                            },
                            {
                                "TargetGroupArn": tgg_b_Arn,#"arn:aws:elasticloadbalancing:us-west-2:123456789012:targetgroup/green-targets/09966783158cda59",
                                "Weight": 10
                            }
                        ]
                    },
                },
            ],
            LoadBalancerArn=elbArn,
            Port=80,
            Protocol='HTTP',
        )
        print("Listeners created...")

        print("Load balencer successfully setup...")

        return dns_publico

# TEM 1 SECURITY GROUP
    def dirty_auto_scaling(self):

        print("\nCreating autoscaling group...")

        print("Finding Load Balancer...")

        response = self.elb.describe_load_balancers(LoadBalancerArns=[self.elbArn])
        dns_name = ""
        for lb in response['LoadBalancers']:
            if lb['LoadBalancerArn'] == self.elbArn:
                print("Load Balancer found...")
                dns_name = lb['DNSName']

        print("Setting gateway IP...")
        if self.gatewayIP == None:
            if len(self.instances_ip) > 0:
                self.gatewayIP = self.instances_ip[0]
                del self.instances_ip[0]

        print("Setting redirect configuration on instance launch...")

        arquivo = open("./initialize_scalable_instance.sh").read()

        arquivo = arquivo[:arquivo.find('\n')] + '\nexport REDIRECTIP="http://' + self.gatewayIP + ':5000"' + arquivo[arquivo.find('\n'):]

        print("Creating instance launch configuration with redirect...")

        self.asg.create_launch_configuration(
            ImageId='ami-04b9e92b5572fa0d1',
            InstanceType="t2.micro",
            UserData = arquivo,
            KeyName=self.nome_chave,
            LaunchConfigurationName='launch-config' + self.seu_nome,
            SecurityGroups = [self.security_group_id],
        )

        print("Attempting to create auto-scaling group with redirecting instances...")

        self.asg.create_auto_scaling_group(AutoScalingGroupName='asg-' + self.seu_nome, LaunchConfigurationName='launch-config' + self.seu_nome, MinSize=1, MaxSize=3, TargetGroupARNs=self.target_group_arns, VPCZoneIdentifier=','.join(self.vpczones))

        print("AutoScaling group created")
