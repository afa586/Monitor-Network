# -*- coding: utf-8 -*-
import os,csv
import subprocess
import time,datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import http.client


# Function to send email
def send_email(subject, body, recipients,priority=3):
    sender_email = config['sender_email']   
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = ', '.join(recipients)
    message['Subject'] = subject
    message.attach(MIMEText(body, 'html'))
    message['X-Priority'] = str(priority)
    with smtplib.SMTP(config['smtp_server']  , 25) as server:
        server.sendmail(sender_email, recipients, message.as_string())

# Function to create email body
def create_mail_body(host,packet_loss,latency,comment,latency_color,packet_loss_color):
    body =  f"""  
    <body>
    <table>

    <tr>
    <th>Host</th>
    <th>Packet Loss(%)</th>
    <th>Latency</th>
    <th>Comment</th>
    </tr>

    <tr>
    <td>{host}</td>
    <td><font color={packet_loss_color}><b>{packet_loss}</b></td>
    <td><font color={latency_color}><b>{latency}</b></td>
    <td>{comment}</td>
    </tr>
    
    </table>
    </br>
    </body>
    </html>
    """
    return """
    <html>
	<style>
	TABLE{border-width: 1px;border-style: solid;border-color: black;border-collapse: collapse}
	TH{border-width: 1px;padding: 2px;border-style: solid;border-color: black;background-color:#99CCFF}
    TD{border-width: 1px;padding: 2px;border-style: solid;border-color: black}
	</style>
    """ + body

# Function to upload data to influxdb
def upload_influxDB(source,host_name,latency,packet_loss):
    conn = http.client.HTTPConnection(config['influxdb_server'], config['influxdb_port'])
    url = f'/write?db={config["db_name"]}'
    data = f'Network-{source},Hostname={host_name} Average={latency},Lost={packet_loss}'
    headers = {'Content-Type': 'application/octet-stream'}
    print(f'Uploading data to influxdb: {data}')
    conn.request("POST", url, body=data.encode(), headers=headers)
    response = conn.getresponse()
    print(response.status, response.reason)
    conn.close()

# Function to write csv file
def write_csv(host_name,latency,packet_loss):
    # get current date
    now = datetime.datetime.now()
    date_string = now.strftime("%Y-%m-%d")
    # create the reports subfolder if it does not exist
    if not os.path.exists('reports'):
        os.makedirs('reports')

    file_path = f'reports/report_{date_string}.csv'
    # Check if the file already exists
    if not os.path.isfile(file_path):
        # If the file does not exist, create it and write the header
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Timestamp', 'Host', 'Latency (ms)', 'Packet Loss (%)'])

    # Append new data to the file
    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([datetime.datetime.now(), host_name, latency, packet_loss])


# Function to monitor
def monitor_hosts(hosts, source,number_to_ping,upload_to_influxDB,need_send_email,remind_period):        
    hostRecovered = {host['name']: True for host in hosts}
    hostDown = {host['name']: False for host in hosts}
    lastAlertTime = {host['name']: None for host in hosts}
    
    while True:
        processes = []
        for host in hosts:
            process = subprocess.Popen(['ping', '-n', number_to_ping, host['name']], stdout=subprocess.PIPE)
            processes.append((host,host['name'], process))
        
        results = []
        for host,host_name, process in processes:
            output = process.communicate()[0]
            output = output.decode()
            
            # Get latency and packet loss
            if 'Average = ' in output:
                latency = float(output.split('Average = ')[1].split('ms')[0])
                packet_loss = float(output.split('Lost = ')[1].split('(')[0])
                if latency > host['thresholds_latency']:
                    latency_color = 'red'
                else:
                    latency_color = 'green'
                if packet_loss > host['thresholds_packet_loss']:
                    packet_loss_color = 'red'
                else:
                    packet_loss_color = 'green'
            else:
                latency = None
                packet_loss = float(100)
                latency_color = 'red'
                packet_loss_color = 'red'
            # Upload data to influxDB
            if upload_to_influxDB:
                if latency is None:
                    upload_influxDB(source,host_name,0,packet_loss)
                else:
                    upload_influxDB(source,host_name,latency,packet_loss)

            # Write history to csv
            write_csv(host_name,latency,packet_loss)
            print(f'{datetime.datetime.now()}: {host_name} - Latency: {latency} ms, Packet Loss: {packet_loss}%')
            
            if need_send_email:
                email_body = create_mail_body(host_name,packet_loss,latency,host['comment'],latency_color,packet_loss_color)
                if packet_loss == 100 or latency == None:                    
                    if not hostDown[host_name]:
                        print(f'Network from {source} to {host_name} is down, sending email!')
                        send_email(f'(Alert)from {source} to {host_name} is down', email_body, host['recipients'],'1')
                        lastAlertTime[host_name] = time.time()
                    elif time.time() - lastAlertTime[host_name] > remind_period:
                        print(f'Network from {source} to {host_name} is bad for long time, sending email!')
                        send_email(f'(Alert)Network from {source} to {host_name} is bad for long time', email_body, host['recipients'],'1')
                        lastAlertTime[host_name] = time.time()
                    hostDown[host_name] = True
                    hostRecovered[host_name] = False                    

                elif latency > host['thresholds_latency'] or packet_loss > host['thresholds_packet_loss']:
                    if hostDown[host_name]:
                        print(f'Network from {source} to {host_name} is up, sending email!')
                        send_email(f'(Alert)Network from {source} to {host_name} is up but performance is bad', email_body, host['recipients'],'1')  
                        lastAlertTime[host_name] = time.time()
                    elif hostRecovered[host_name]:
                        print(f'Network from {source} to {host_name} is bad, sending email!')
                        send_email(f'(Alert)Network from {source} to {host_name} is bad', email_body, host['recipients'],'1')
                        lastAlertTime[host_name] = time.time()
                    elif lastAlertTime[host_name] is not None:
                        if time.time() - lastAlertTime[host_name] > remind_period:
                            print(f'Network from {source} to {host_name} is bad for long time, sending email!')
                            send_email(f'(Alert)Network from {source} to {host_name} is bad for long time', email_body, host['recipients'],'1')
                            lastAlertTime[host_name] = time.time()
                    hostDown[host_name] = False
                    hostRecovered[host_name] = False

                else:
                    if hostDown[host_name]:
                        print(f'Network from {source} to {host_name} is up, sending email!')
                        send_email(f'(OK)Network from {source} to {host_name} is up', email_body, host['recipients'],'3')  
                    elif not hostRecovered[host_name]:
                        print(f'Network from {source} to {host_name} recovered, sending email!')
                        send_email(f'(OK)Network from {source} to {host_name} recovered', email_body, host['recipients'],'3')
                    hostDown[host_name] = False
                    hostRecovered[host_name] = True
                    lastAlertTime[host_name] = None
                
                # time.sleep(intervals[host])

if __name__ == '__main__': 
    import json
    def load_config(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    config_path = 'config.json'
    config = load_config(config_path)
    monitor_hosts(config['hosts'],config['source'],config['number_to_ping'],config['upload_to_influxDB'],config['need_send_email'],config['remind_period'])
    
    