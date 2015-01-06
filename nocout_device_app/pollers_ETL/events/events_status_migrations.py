"""
This file is the main file for migrating the mongodb data to mysql data for ping services and other services.It reads all configuration required for connecting the db from config.ini

File also migrates the mongodb data for the latest enrty for each devices to mysql data .so in mysql status tables store the latest data entry 
for each device
"""

from nocout_site_name import *
import imp

config_module = imp.load_source('configparser', '/omd/sites/%s/nocout/configparser.py' % nocout_site_name)

def main():
    mongo_conf = []
    configs = config_module.parse_config_obj()
    for section, options in configs.items():
        mongo_conf.append((options.get('site'),options.get('host'), options.get('port')))
	
    # Get site specific mongo conf
    service_event_status_script = configs.get(mongo_conf[0][0]).get('service_event_status').get('script')
    service_event_status_script = __import__(service_event_status_script)
    service_event_status_script.main(mongo_conf=mongo_conf,
    user=configs.get(mongo_conf[0][0]).get('user'),
    sql_passwd=configs.get(mongo_conf[0][0]).get('sql_passwd'),
    nosql_db=configs.get(mongo_conf[0][0]).get('nosql_db'),
    sql_port=configs.get(mongo_conf[0][0]).get('mysql_port'),
    sql_db=configs.get(mongo_conf[0][0]).get('sql_db'), table_name=configs.get(mongo_conf[0][0]).get('service_event_status').get('table_name'), ip=configs.get(mongo_conf[0][0]).get('ip')
    )
	
    network_event_status_script = configs.get(mongo_conf[0][0]).get('network_event_status').get('script')
    network_event_status_script = __import__(network_event_status_script)
    network_event_status_script.main(mongo_conf=mongo_conf,
    user=configs.get(mongo_conf[0][0]).get('user'),
    sql_passwd=configs.get(mongo_conf[0][0]).get('sql_passwd'),
    nosql_db=configs.get(mongo_conf[0][0]).get('nosql_db'),
    sql_port=configs.get(mongo_conf[0][0]).get('mysql_port'),
    sql_db=configs.get(mongo_conf[0][0]).get('sql_db'), table_name=configs.get(mongo_conf[0][0]).get('network_event_status').get('table_name'), ip=configs.get(mongo_conf[0][0]).get('ip')
    )

	

if __name__ == '__main__':
    main()
