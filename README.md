# Monitor-Network
The code provided is a network monitoring script written in Python. Here is a concise summary of what the code does:

It imports necessary modules such as os, csv, json, time, datetime, smtplib, http.client, concurrent.futures, icmplib, logging, and traceback.
It configures logging to write errors to the "errors.log" file.
It defines a function send_email to send email notifications.
It defines a function create_mail_body to create the body of the email notification.
It defines a function upload_influxDB to upload data to an InfluxDB database.
It defines a function write_csv to write data to a CSV file.
It defines a function ping_host to ping a host and retrieve latency and packet loss information.
It defines a function monitor_network to continuously monitor the network by pinging the specified hosts and performing various actions based on the results.
The main part of the script reads the configuration from a "config.json" file, retrieves the host information, and starts monitoring the network using the monitor_network function.
