"""
inventory_mongo_migration.py

File contains the data migrations of mongodb to mysql db for inventory services. Inventory services run once a day.

"""
import MySQLdb
from datetime import datetime, timedelta
from rrd_migration import mongo_conn
import socket

def main(**configs):
    """
    Main function for reading the data from mongodb database for inventory services.After reading the data ,it is formatted according to mysql
    table schema and inserted into mysql db
    Args: Multiple argument fetched from config.ini
    Return : None
    Raises: No exception
    """
    data_values = []
    values_list = []
    docs = []
    db = mysql_conn(configs=configs)
    # Get the time for latest entry in mysql
    #start_time = get_latest_entry(db_type='mysql', db=db, site=configs.get('site'),table_name=configs.get('table_name'))
    utc_time = datetime(1970, 1,1,5,30)


    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=1440)
    start_epoch = int((start_time - utc_time).total_seconds())
    end_epoch =  int((end_time - utc_time).total_seconds())
    print start_time,end_time
    docs = read_data(start_epoch, end_epoch, configs=configs)
    for doc in docs:
        values_list = build_data(doc)
        data_values.extend(values_list)
    field_names = [
        'host_name',
        'service',
        'host_address',
        'site_id',
        'value',
        'war',
        'crit',
	'service_state',
        'time',
    ]
    insert_data(configs.get('table_name'), data_values, configs=configs)
    print "Data inserted into performance_performanceinventory table"
    

def read_data(start_time, end_time, **kwargs):

    """
    function for reading the data from mongodb database for inventory services.After reading the data
    Args: start_time (time of last record enrty)
    Kwargs: end_time(current time) ,multiple arguments fetched from config.ini
    Return : None
    Raises: No exception

    """
    db = None
    port = None
    docs = []
    #end_time = datetime(2014, 6, 26, 18, 30)
    #start_time = end_time - timedelta(minutes=10)
    docs = [] 
    db = mongo_conn(
        host=kwargs.get('configs').get('host'),
        port=int(kwargs.get('configs').get('port')),
        db_name=kwargs.get('configs').get('nosql_db')
    )
    if db:
        cur = db.nocout_inventory_service_perf_data.find({
            "check_timestamp": {"$gt": start_time, "$lt": end_time}
        })
        for doc in cur:
            docs.append(doc)
     
    return docs

def build_data(doc):
	"""
	function for building the data based on the collected record from mongodb database for inventory services.
	Arg: doc (extracted doc from the mongodb )
	Kwargs: None
	Return : formatted record for the mysql
	Raises: No exception
	"""
	values_list = []
	time = doc.get('time')
	machine_name = get_machine_name()
        t = (
        doc.get('device_name'),
        doc.get('service_name'),
        doc.get('sys_timestamp'),
        doc.get('check_timestamp'),
        doc.get('current_value'),
        doc.get('min_value'),
        doc.get('max_value'),
        doc.get('avg_value'),
        doc.get('warning_threshold'),
        doc.get('critical_threshold'),
        doc.get('severity'),
        doc.get('site_name'),
        doc.get('data_source'),
        doc.get('ip_address'),
        machine_name
        )
	values_list.append(t)
	t = ()
	return values_list

def insert_data(table, data_values, **kwargs):
	"""
	function for building the data based on the collected record from mongodb database for inventory services.
	Arg: table (mysql database table name)
	Kwargs: data_values (formatted record)
	Return : None
	Raises: MySQLdb.error
	"""
	db = mysql_conn(configs=kwargs.get('configs'))
	query = 'INSERT INTO `%s` ' % table
	query += """
                (device_name,service_name,sys_timestamp,check_timestamp,
                current_value,min_value,max_value,avg_value,warning_threshold,
                critical_threshold,severity,site_name,data_source,
                ip_address,machine_name)
                VALUES(%s,%s, %s, %s, %s, %s, %s,%s,%s,%s,%s,%s,%s,%s,%s)
                """
	cursor = db.cursor()
    	try:
        	cursor.executemany(query, data_values)
    	except MySQLdb.Error, e:
        	raise MySQLdb.Error, e
    	db.commit()
    	cursor.close()

def get_epoch_time(datetime_obj):
    """
	function for converting the datetime object into epoch_time.
	Arg: datetime_obj (time object)
	Kwargs: None
	Return : epoch_time/datetimeobj
	Raises: None
    """
    # Get India times (GMT+5.30)
    utc_time = datetime(1970, 1,1, 5, 30)
    if isinstance(datetime_obj, datetime):
        epoch_time = int((datetime_obj - utc_time).total_seconds())
        return epoch_time
    else:
        return datetime_obj

def mysql_conn(db=None, **kwargs):
    """
	function for mysql connection.
	Arg: db (database instance obj)
	Kwargs: multiple arguments for mysql connections
	Return : db object
	Raises: MYSQLdb.error
    """
    try:
        db = MySQLdb.connect(host=kwargs.get('configs').get('host'), user=kwargs.get('configs').get('user'),
            passwd=kwargs.get('configs').get('sql_passwd'), db=kwargs.get('configs').get('sql_db'))
    except MySQLdb.Error, e:
        raise MySQLdb.Error, e

    return db
def get_machine_name(machine_name=None):
    """
	function for getting machine_name.
	Arg: machine_name
	Kwargs: None
	Return : machine_name
	Raises: Exception
    """
    try:
        machine_name = socket.gethostname()
    except Exception, e:
        raise Exception(e)

    return machine_name


if __name__ == '__main__':
    main()
