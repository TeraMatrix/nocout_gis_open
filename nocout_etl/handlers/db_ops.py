"""
db_ops.py
==========

Maintains per process database connections and handles 
data manipulations, used in site-wide ETL operations.
[for celery]
"""


from redis import StrictRedis
from pymongo import MongoClient
from mysql.connector import connect

from ConfigParser import ConfigParser
from itertools import groupby
from operator import itemgetter
from ast import literal_eval

from celery import Task
from celery.contrib.methods import task_method
from celery.utils.log import get_task_logger

from start import app

logger = get_task_logger(__name__)
info , warning, error = logger.info, logger.warning, logger.error

db_conf = app.conf.CNX_FROM_CONF

class DatabaseTask(Task):
	abstract = True
	# maintains database connections based on sites
	# mysql connections
	my_conn_pool = {}
	# mongo connections
	mo_conn_pool = {}
	# redis connection object
	redis_conn = None
	# mongo connection object
	#mongo_db = None
	# mysql connection object
	#mysql_db = None

	conf = ConfigParser()
	conf.read(db_conf)


	#@property
	def mongo_cnx(self, key):
		# mongo connection config
		mo_conf = {
				'host': self.conf.get(key, 'mongo_host'),
				'port': int(self.conf.get(key, 'mongo_port')),
				}
		if not self.mo_conn_pool.get(key):
			try:
				self.mo_conn_pool[key] = MongoClient(**mo_conf)[self.conf.get(key, 
					'mongo_database')]
			except Exception as exc:
				error('Mongo connection error... {0}'.format(exc))
				#raise self.retry(max_retries=2, countdown=10, exc=exc)

		return self.mo_conn_pool.get(key)

	#@property
	def mysql_cnx(self, key):
		# mysql connection config
		my_conf = {
				'host': self.conf.get(key, 'host'),
				'port': int(self.conf.get(key, 'port')),
				'user': self.conf.get(key, 'user'),
				'password': self.conf.get(key, 'password'),
				'database': self.conf.get(key, 'database'),
				}
		try_connect = False
		if not (self.my_conn_pool.get(key) and self.my_conn_pool.get(key).is_connected()):
			try_connect = True
		if try_connect:
			try:
				self.my_conn_pool[key] = connect(**my_conf)
			except Exception as exc:
				error('Mysql connection problem, retrying... {}'.format(exc))
				#raise self.retry(max_retries=2, countdown=10, exc=exc)

		return self.my_conn_pool.get(key)


class RedisInterface:
	""" Implements various redis operations"""

	def __init__(self, **kw):
		self.custom_conf = kw.get('custom_conf')
		self.redis_conn = None
		# queue name to get check results data from 
		self.perf_q = kw.get('perf_q')

	@property
	def redis_cnx(self):
		conf = ConfigParser()
		conf.read(db_conf)
		# redis connection config
		re_conf = {
			'port': int(conf.get('redis', 'port')),
			'db': int(conf.get('redis', 'db'))
		}
		re_conf.update(self.custom_conf) if self.custom_conf else re_conf
		try:
			self.redis_conn = StrictRedis(**re_conf)
		except Exception as exc:
			error('Redis connection error... {0}'.format(exc))
		if not self.redis_conn:
			pass

		return self.redis_conn

	def get(self, start, end):
		""" Get and remove values from redis list based on a range"""
		info('Get data from queue: {0}'.format(self.perf_q))
		output = self.redis_cnx.lrange(self.perf_q, start, end)
		# keep only unread values in list
		self.redis_cnx.ltrim(self.perf_q, end+1, -1)

		return output

	@app.task(filter=task_method, name='redis-update')
	def redis_update(self, data_values, update_queue=False, perf_type=''):
		""" Updates multiple hashes in single operation using pipelining"""
		KEY = '%s:%s:%s:%s' % (perf_type, '%s', '%s', '%s')
		p = self.redis_cnx.pipeline(transaction=True)
		try:
			# update the queue values
			if update_queue:
				KEY = '%s:%s:%s' % (perf_type, '%s', '%s')
				devices = [d.get('device_name') for d in data_values]
				# push the values into queues
				[p.rpush(KEY % (d.get('device_name'), d.get('service_name')), d.get('severity'))
				 for d in data_values]
				# perform all operations atomically
				p.execute()
				# calc queue length corresponds to every host entry
				[p.llen(KEY % x) for x in devices]
				queues_len = p.execute()
				host_queuelen_map = zip(devices, queues_len)
				# keep only 2 latest values for each host entry, if any
				trim_hosts = filter(lambda x: x[1] > 2, host_queuelen_map)
				[p.ltrim(KEY % x[1], -2, -1) for x in trim_hosts]
				p.execute()

			# update the hash values
			else:
				[p.hmset(KEY %
					(d.get('device_name'), d.get('service_name'), d.get('data_source')),
					d) for d in data_values]
				# perform all operations atomically
				p.execute()
		except Exception as exc:
			error('Redis pipe error in update... {0}, retrying...'.format(exc))
			# send the task for retry
			Task.retry(args=(data_values), kwargs={'perf_type': perf_type},
					max_retries=2, countdown=10, exc=exc)

	def multi_get(self, key_prefix):
		""" Returns list of values (mappings) having keys matching with key_prefix"""
		out = []
		if not key_prefix:
			return out
		pattern = key_prefix + '*'
		keys = self.redis_cnx.keys(pattern=pattern)
		p = self.redis_cnx.pipeline()
		try:
			[p.hgetall(k) for k in keys]
			out = literal_eval(p.execute())
		except Exception as exc:
			error('Redis pipe error in multi get... {0}'.format(exc))

		return out

	@app.task(filter=task_method, name='redis-insert')
	def multi_set(self, data_values, perf_type=''):
		""" Sets multiple key values through pipeline"""
		KEY = '%s:%s:%s' % (perf_type, '%s', '%s')
		p = self.redis_cnx.pipeline(transaction=True)
		# keep the provis data keys with a timeout of 5 mins
		[p.setex(KEY %
		         (d.get('device_name'), d.get('service_name')),
		         300, d.get('current_value')) for p in data_values
		 ]


@app.task(base=DatabaseTask, name='load-inventory', bind=True)
def load_inventory(self):
	"""
	Loads inventory data into redis
	"""
	query = (
		"SELECT DISTINCT D.device_name, site_instance_siteinstance.name, "
		"D.ip_address, device_devicetype.name AS dev_type, "
		"device_devicetechnology.name AS dev_tech "
		"FROM device_device D "
		"INNER JOIN "
		"(device_devicetype, device_devicetechnology, machine_machine, "
		"site_instance_siteinstance) "
		"ON "
		"( "
		"device_devicetype.id = D.device_type AND "
		"device_devicetechnology.id = D.device_technology AND "
		"machine_machine.id = D.machine_id AND "
		"site_instance_siteinstance.id = D.site_instance_id "
		") "
		"WHERE "
		"D.is_deleted = 0 AND "
		"D.host_state <> 'Disable' AND "
		"device_devicetechnology.name IN ('WiMAX', 'P2P', 'PMP', 'Mrotek', 'RiCi')"
	)
	dr_query = (
		"SELECT "
		"inner_device.Sector_IP AS primary_ip, "
		"outer_device.ip_address AS dr_ip "
		"FROM ( "
			"SELECT "
				"ds.ip_address AS Sector_IP, "
				"sector.dr_configured_on_id as dr_id "
		"FROM "
			"inventory_sector AS sector "
		"INNER JOIN "
			"device_device AS ds "
		"ON "
			"NOT ISNULL(sector.sector_configured_on_id) "
		"AND "
			"sector.sector_configured_on_id = ds.id "
		"AND "
			"sector.dr_site = 'yes' "
		"AND "
			"NOT ISNULL(sector.dr_configured_on_id) "
		") AS inner_device "
		"INNER JOIN "
			"device_device as outer_device "
		"ON "
			"outer_device.id = inner_device.dr_id; "
	)

	cur = load_inventory.mysql_cnx('historical').cursor()
	cur.execute(query)
	out = cur.fetchall()
	#info('out: {0}'.format(out))

	# keeping invent data in database number 3
	rds_cli = RedisInterface(custom_conf={'db': 3})
	rds_cli.redis_cnx.flushdb()
	rds_pipe = rds_cli.redis_cnx.pipeline(transaction=True)
	wimax_bs_list = []
	# group based on device technologies and load the devices info to redis
	for grp, grp_vals in groupby(out, key=itemgetter(4)):
		grouped_devices = list(grp_vals)
		if grouped_devices[0][3] == 'StarmaxIDU':
			[wimax_bs_list.append(list(x)) for x in grouped_devices]
			# push wimax bs with its dr site info
			cur.execute(dr_query)
			dr_info = cur.fetchall()
			load_devicetechno_wise(grp, wimax_bs_list, rds_pipe, extra=dr_info)
		else:
			load_devicetechno_wise(grp, grouped_devices, rds_pipe)
	try:
		rds_pipe.execute()
	except Exception as exc:
		error('Error in redis inventory loading... {0}'.format(exc))
	cur.close()


@app.task(name='load-devicetechno-wise')
def load_devicetechno_wise(device_techno, data_values, p, extra=None):
	"""
	Loads specific device type data into redis
	"""
	t = data_values[0]
	KEY = '%s:%s:%s' % (str(t[4]).lower(),
					'ss' if t[3].endswith('SS') else 'bs',
					'%s')
	# entries needed from index 0 to last_index-1
	last_index = 3
	matched_dr = None
	# TODO: need to improve the algo here
	if extra:
		last_index = 4
		for outer in data_values:
			del outer[3:]
			for inner in extra:
				if inner[0] == outer[2]:
					matched_dr = inner[1]
					break
			if matched_dr:
				outer.append(matched_dr)
				matched_dr = None
	[p.rpush(KEY % data[2], data[:last_index]) for data in data_values]


@app.task(base=DatabaseTask, name='nw-mongo-update', bind=True)
def mongo_update(self, data_values, indexes, col, site):
	lcl_cnx = mongo_update.mongo_cnx(site)[col]
	if data_values and lcl_cnx:
		try:
			for val in data_values:
				find_query = {}
				[find_query.update({x: val.get(x)}) for x in indexes]
				lcl_cnx.update(find_query, val, upsert=True)
		except Exception as exc:
			error('Mongo update problem, retrying... {}'.format(exc))
			raise self.retry(args=(data_values, indexes, col), max_retries=1,
					countdown=10, exc=exc)
	else:
		# TODO :: mark the task as failed
		error('Mongo update failed...')


@app.task(base=DatabaseTask, name='nw-mongo-insert', bind=True)
def mongo_insert(self, data_values, col, site):
	if data_values:
		try:
			mongo_insert.mongo_cnx(site)[col].insert(data_values)
		except Exception as exc:
			error('Mongo insert problem, retrying... {}'.format(exc))
			raise self.retry(args=(data_values, col), max_retries=1,
					exc=exc)
	else:
		# TODO :: mark the task as failed
		error('Mongo insert failed...')


@app.task(base=DatabaseTask, name='nw-mysql-handler', bind=True)
def mysql_insert_handler(self, data_values, insert_table, update_table, mongo_col, 
		site, columns=None):
	""" mysql insert and also updates last entry into mongodb"""
	
	# TODO: Every task should sub class db_ops and initialize table names, 
	# instead of passing them as function args seperately
	# TODO :: remove this extra iteration
	for entry in data_values:
		entry.pop('_id', '')
		entry['sys_timestamp'] = entry['sys_timestamp'].strftime('%s')
		entry['check_timestamp'] = entry['check_timestamp'].strftime('%s')

	try:
		# executing the task locally
		mysql_insert.s(insert_table, data_values, site).apply()
	except Exception as exc:
		#lcl_cnx.rollback()
		# may be retry
		error('Mysql insert problem... {}'.format(exc))

	else:
		# timestamp of most latest insert made to mysql
		last_timestamp = latest_entry(site, op='S', perf_type=insert_table) 
		# last timestamp for this insert
		last_timestamp_local = float(data_values[-1].get('sys_timestamp'))
		if (last_timestamp and ((last_timestamp + 900) < last_timestamp_local)):
			warning('last_timestamp {}'.format(last_timestamp))
			warning('last_timestamp_local {}'.format(last_timestamp_local))
			# mysql is down for more than 15 minutes from now,
			# import data from mongo
			rds_cli = StrictRedis(port=app.conf.REDIS_PORT)
			lock = rds_cli.lock('mongo-mysql-export', timeout=5*60)
			have_lock = lock.acquire(blocking=False)
			# ensure, only one task is executed at one time
			if have_lock:
				mongo_export_mysql(last_timestamp, last_timestamp_local,
						mongo_col, insert_table, site)
		
		# update the `latest_entry` collection
		latest_entry(site, op='I', value=last_timestamp_local, perf_type=insert_table)

	# sending a message for task, execute asynchronously
	mysql_update.s(update_table, data_values, site, columns=columns
			).apply_async()


@app.task(base=DatabaseTask, name='nw-mysql-update', bind=True)
def mysql_update(self, table, data_values, site, columns=None):
	""" mysql update"""
	
	default_columns = ('device_name', 'service_name', 'machine_name',
			'site_name', 'ip_address', 'data_source', 'severity',
			'current_value', 'min_value', 'max_value', 'avg_value',
			'warning_threshold', 'critical_threshold', 'sys_timestamp',
			'check_timestamp', 'age', 'refer')
	columns = columns if columns else default_columns
	p0 = "INSERT INTO %(table)s" % {'table': table}
	p1 = ' (%s)' % ','.join(columns)
	p2 = ' , '.join(map(lambda x: ' %('+ x + ')s', columns))
	p3 = ' , '.join(map(lambda x: x + ' = VALUES(' + x + ')', columns))
	updt_qry = p0 + p1 + ' VALUES (' + p2 + ') ON DUPLICATE KEY UPDATE ' + p3
	info('Update query: {0}'.format(updt_qry))

	#updt_qry += """
	#		(
	#			device_name, 
	#			service_name, 
	#			machine_name,
	#			site_name, 
	#			ip_address, 
	#			data_source, 
	#			severity, 
	#			current_value,
	#			min_value, 
	#			max_value, 
	#			avg_value, 
	#			warning_threshold, 
	#			critical_threshold, 
	#			sys_timestamp, 
	#			check_timestamp, 
	#			age, 
	#			refer
	#		) 
	#		VALUES 
	#		(
	#			%(device_name)s, 
	#			%(service_name)s, 
	#			%(machine_name)s, 
	#			%(site_name)s, 
	#			%(ip_address)s, 
	#			%(data_source)s, 
	#			%(severity)s, 
	#			%(current_value)s, 
	#			%(min_value)s, 
	#			%(max_value)s, 
	#			%(avg_value)s, 
	#			%(warning_threshold)s, 
	#			%(critical_threshold)s, 
	#			%(sys_timestamp)s, 
	#			%(check_timestamp)s, 
	#			%(age)s, 
	#			%(refer)s
	#		)
	#		ON DUPLICATE KEY UPDATE
	#		machine_name = VALUES(machine_name),
	#		site_name 	 = VALUES(site_name), 
	#		ip_address 	 = VALUES(ip_address), 	
	#		severity 	 = VALUES(severity), 
	#		current_value  = VALUES(current_value),
	#		min_value 	 = VALUES(min_value), 
	#		max_value 	 = VALUES(max_value), 
	#		avg_value 	 = VALUES(avg_value), 
	#		warning_threshold = VALUES(warning_threshold), 
	#		critical_threshold = VALUES(critical_threshold), 
	#		sys_timestamp  = VALUES(sys_timestamp), 
	#		check_timestamp = VALUES(check_timestamp), 
	#		age 		 = VALUES(age), 
	#		refer 		 = VALUES(refer)
	#		"""
		  
	try:
		lcl_cnx = mysql_update.mysql_cnx(site)
		cur = lcl_cnx.cursor()
		cur.executemany(updt_qry, data_values)
		lcl_cnx.commit()
		cur.close()
	except Exception as exc:
		# rollback transaction
		lcl_cnx.rollback()
		# attempt task retry
		raise self.retry(args=(table, data_values, site), max_retries=1, countdown=10, 
				exc=exc)

	warning('Len for status upserts {}\n'.format(len(data_values)))


@app.task(base=DatabaseTask, name='nw-mysql-insert', bind=True)
def mysql_insert(self, table, data_values, site):
	""" mysql batch insert"""
	
	# TODO :: custom option for retries
	try:
		fmt_qry = "INSERT INTO %(table)s " % {'table': table}
		fmt_qry += """
				(device_name, service_name, machine_name,
				site_name, ip_address, data_source, severity, current_value,
				min_value, max_value, avg_value, warning_threshold, 
				critical_threshold, sys_timestamp, check_timestamp, age, refer) 
				VALUES 
				(%(device_name)s, %(service_name)s, %(machine_name)s, %(site_name)s, 
				%(ip_address)s, %(data_source)s, %(severity)s, %(current_value)s, 
				%(min_value)s, %(max_value)s, %(avg_value)s, %(warning_threshold)s, 
				%(critical_threshold)s, %(sys_timestamp)s, %(check_timestamp)s, 
				%(age)s, %(refer)s)
				"""
		lcl_cnx = mysql_insert.mysql_cnx(site)
		cur = lcl_cnx.cursor()
		#cur.executemany(qry, map(lambda x: fmt_qry(**x), data_values))
		cur.executemany(fmt_qry, data_values)
		lcl_cnx.commit()
		cur.close()
	except Exception as exc:
		# rollback transaction
		lcl_cnx.rollback()
		error('Error in mysql_insert task, {}'.format(exc))


@app.task(base=DatabaseTask, name='get-latest-entry', bind=True)
def latest_entry(self, site, op='S', value=None, perf_type=None):
	""" stores timestamp of last successful insert made into mysql"""
	lcl_cnx = latest_entry.mongo_cnx(site)
	stamp = None
	if op == 'S':
		# select operation
		try:
			stamp = list(lcl_cnx['latest_entry'].find(
				{'perf_type': perf_type}))[0].get('time')
		except: pass
	elif op == 'I':
		# insert operation
		lcl_cnx['latest_entry'].update({'perf_type': perf_type}, 
				{'time': value, 'perf_type': perf_type}, upsert=True)

	return float(stamp) if stamp else stamp


@app.task(base=DatabaseTask, name='mongo-export-mysql', bind=True)
def mongo_export_mysql(self, start_time, end_time, col, table, site):
	""" Export old data which is not in mysql due to its downtime"""
	
	warning('Mongo export mysql called')
	data_values = list(mongo_export_mysql.mongo_cnx(site)[col].find(
			{'local_timestamp': {'$gt': start_time, '$lt': end_time}}))
	warning('Import {0} values to mysql'.format(len(data_values)))

	# TODO :: data should be sent into batches
	# or send the task into celery chuncks, dont execute the task locally
	if data_values:
		mysql_insert.s('performance_performancenetwork', data_values, site).apply_async()

