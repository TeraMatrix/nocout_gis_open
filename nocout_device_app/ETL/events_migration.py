from configparser import parse_config_obj


def main():
    configs = parse_config_obj()
    for section, options in configs.items():
	network_event_script = options.get('network_event').get('script')
        network_event_migration_script = __import__(network_event_script)
        network_event_migration_script.main(site=options.get('site'), host=options.get('host'),
                user=options.get('user'), port=options.get('port'),
                sql_passwd=options.get('sql_passwd'),
                nosql_db=options.get('network_event').get('nosql_db'),
                sql_db=options.get('network_event').get('sql_db'), table_name=options.get('network_event').get('table_name'), ip=options.get('ip')
        )

        service_event_script = options.get('service_event').get('script')
        service_event_migration_script = __import__(service_event_script)
        service_event_migration_script.main(site=options.get('site'), host=options.get('host'),
                user=options.get('user'), port=options.get('port'),
                sql_passwd=options.get('sql_passwd'),
                nosql_db=options.get('service_event').get('nosql_db'),
                sql_db=options.get('service_event').get('sql_db'), table_name=options.get('service_event').get('table_name'),
                ip=options.get('ip')
        )

if __name__ == '__main__':
    main()
