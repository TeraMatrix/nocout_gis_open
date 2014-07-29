from configparser import parse_config_obj


def main():
    configs = parse_config_obj()
    for section, options in configs.items():
        
	network_script = options.get('network').get('script')
	network_migration_script = __import__(network_script)
	network_migration_script.main(site=options.get('site'), host=options.get('host'),
		user=options.get('user'), port=options.get('port'),
		sql_passwd=options.get('sql_passwd'),
		nosql_db=options.get('network').get('nosql_db'),
		sql_db=options.get('network').get('sql_db'), table_name=options.get('network').get('table_name'), ip=options.get('ip')
        )

	service_script = options.get('service').get('script')
	service_migration_script = __import__(service_script)
	service_migration_script.main(site=options.get('site'), host=options.get('host'),
	    	user=options.get('user'), port=options.get('port'),
            	sql_passwd=options.get('sql_passwd'),
            	nosql_db=options.get('service').get('nosql_db'),
            	sql_db=options.get('service').get('sql_db'), table_name=options.get('service').get('table_name'), ip=options.get('ip')
        )
	
	service_status_tables_script = options.get('service_status_tables').get('script')
        service_status_tables_migration_script = __import__(service_status_tables_script)
        service_status_tables_migration_script.main(site=options.get('site'), host=options.get('host'),
        	user=options.get('user'), port=options.get('port'),
             	sql_passwd=options.get('sql_passwd'),
                nosql_db=options.get('service_status_tables').get('nosql_db'),
                sql_db=options.get('service_status_tables').get('sql_db'), table_name=options.get('service_status_tables').get('table_name'), 
		ip=options.get('ip')
        )

	network_status_tables_script = options.get('network_status_tables').get('script')
        network_status_tables_migration_script = __import__(network_status_tables_script)
        network_status_tables_migration_script.main(site=options.get('site'), host=options.get('host'),
        	user=options.get('user'), port=options.get('port'),
             	sql_passwd=options.get('sql_passwd'),
                nosql_db=options.get('network_status_tables').get('nosql_db'),
                sql_db=options.get('network_status_tables').get('sql_db'), table_name=options.get('network_status_tables').get('table_name'), 
		ip=options.get('ip')
        )

if __name__ == '__main__':
    main()
