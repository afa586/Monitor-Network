# -*- coding: utf-8 -*-
import os,csv,json
import time,datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import http.client
from concurrent.futures import ThreadPoolExecutor
import icmplib
import logging,traceback

# configure logging
logging.basicConfig(filename='errors.log', level=logging.ERROR)


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
        writer.writerow([now.strftime('%Y-%m-%d %H:%M:%S'), host_name, latency, packet_loss])

# Function to ping host
def ping_host(host):
    host_name = host['name']
    response = icmplib.ping(host_name, count=config["number_to_ping"])
    if response.is_alive:
        latency = int(response.avg_rtt)
    else:
        latency = None        
    packet_loss = int(response.packet_loss * 100)
    return (host, latency, packet_loss)

# Function to loop and analyze results
def monitor_network(hosts):
    hostRecovered = {host['name']: True for host in hosts}
    hostDown = {host['name']: False for host in hosts}
    lastBadTime = {host['name']: None for host in hosts}
    lastDownTime = {host['name']: None for host in hosts}
    # Loop indefinitely
    while True:
        try:
            # Ping all hosts concurrently
            with ThreadPoolExecutor() as executor:
                results = executor.map(ping_host, hosts)
        
            for result in results:
                host = result[0]
                host_name = host['name']
                latency = result[1]
                packet_loss = result[2]
                if int(packet_loss) == 100:
                    latency_color = 'red'
                elif latency > host['thresholds_latency']:
                    latency_color = 'red'
                else:
                    latency_color = 'green'
                if packet_loss > host['thresholds_packet_loss']:
                    packet_loss_color = 'red'
                else:
                    packet_loss_color = 'green'

                # Write history to csv
                write_csv(host_name,latency,packet_loss)
                print(f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}: {host_name} - Latency: {latency} ms, Packet Loss: {packet_loss}%')

                # Upload data to influxDB
                if config['upload_to_influxDB']:
                    if latency is None:
                        upload_influxDB(config['source'],host_name,0,packet_loss)
                    else:
                        upload_influxDB(config['source'],host_name,latency,packet_loss)

                
                #  Send email alert 
                if config['need_send_email']:
                    email_body = create_mail_body(host_name,packet_loss,latency,host['comment'],latency_color,packet_loss_color)
                    email_recipients =  host['recipients']
                    if packet_loss == 100 or latency == None:                    
                        if not hostDown[host_name]:
                            email_subject = f'(Alert)Network from {config["source"]} to {host_name} is down'
                            print(f'{email_subject}, sending email!')
                            send_email(email_subject, email_body, email_recipients,'1')
                        elif lastDownTime[host_name] is not None:
                            if time.time() - lastDownTime[host_name] > config['remind_period']:
                                email_subject = f'(Alert)Network from {config["source"]} to {host_name} is bad for long time'
                                print(f'{email_subject}, sending email!')
                                send_email(email_subject, email_body, email_recipients,'1')                            
                        hostDown[host_name] = True
                        hostRecovered[host_name] = False  
                        lastDownTime[host_name] = time.time()                  

                    elif latency > host['thresholds_latency'] or packet_loss > host['thresholds_packet_loss']:
                        if hostDown[host_name]:
                            email_subject = f'(Alert)Network from {config["source"]} to {host_name} is up but performance is bad'
                            print(f'{email_subject}, sending email!')
                            send_email(email_subject, email_body, email_recipients,'1')  
                            lastDownTime[host_name] = None
                        elif hostRecovered[host_name]:
                            email_subject = f'(Alert)Network from {config["source"]} to {host_name} is bad'
                            print(f'{email_subject}, sending email!')
                            send_email(email_subject, email_body, email_recipients,'1')
                        elif lastBadTime[host_name] is not None:
                            if time.time() - lastBadTime[host_name] > config['remind_period']:
                                email_subject = f'(Alert)Network from {config["source"]} to {host_name} is bad for long time'
                                print(f'{email_subject}, sending email!')
                                send_email(email_subject, email_body, email_recipients,'1')                            
                        hostDown[host_name] = False
                        hostRecovered[host_name] = False
                        lastBadTime[host_name] = time.time()

                    else:
                        if hostDown[host_name]:
                            email_subject = f'(OK)Network from {config["source"]} to {host_name} is up'
                            print(f'{email_subject}, sending email!')
                            send_email(email_subject, email_body, email_recipients)
                        elif not hostRecovered[host_name]:
                            email_subject = f'(OK)Network from {config["source"]} to {host_name} recovered'
                            print(f'{email_subject}, sending email!')
                            send_email(email_subject, email_body, email_recipients)
                        hostDown[host_name] = False
                        hostRecovered[host_name] = True
                        lastBadTime[host_name] = None
                        lastDownTime[host_name] = None
            
            # Sleep 1 minutes
            print(f'Sleep {config["time_to_sleep"]}s') 
            time.sleep(config["time_to_sleep"])
        except Exception as e:
            logging.error(f"An error occurred: {e}\nTime of occurrence: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{traceback.format_exc()}")
           
    

if __name__ == '__main__': 
    # Read configuration file
    with open("config.json", "r") as f:
        config = json.load(f)
    hosts = config['hosts']
    monitor_network(hosts)

    