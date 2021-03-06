import  sys
import os
from airflow.models import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators.python_operator import BranchPythonOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.subdag_operator import SubDagOperator
from cm_sub_dag_import_huawei_gexport_files import import_huawei_gexport_parsed_csv

sys.path.append('/mediation/packages');

from bts import NetworkBaseLine, Utils, ProcessCMData;


bts_utils = Utils();


def parse_and_import_huawei_gexport(parent_dag_name, child_dag_name, start_date, schedule_interval):

    dag_id = '%s.%s' % (parent_dag_name, child_dag_name)

    dag = DAG(
        '%s.%s' % (parent_dag_name, child_dag_name),
        schedule_interval=schedule_interval,
        start_date=start_date,
    )

    task_clean_mo_names = BashOperator(
        task_id='clean_gexport_mo_names',
        bash_command=r"""
sed -i -r "
s/_(BSC6900GSM|BSC6900UMTS|BSC6900GU|BSC6910GSM|BSC6910UMTS|BSC6910GU)//ig;
s/_(BTS3900|PICOBTS3900|BTS3911B|PICOBTS3911B|MICROBTS3900|MICROBTS3911B)//ig;
s/BSC(6910|6900)(UMTS|GSM)Function/FUNCTION/ig;
s/BSC(6910|6900)Equipment/EQUIPMENT/ig;
s/<class name=\"(.*)\"/<class name=\"\U\1\"/ig;
s/<class name=\"(.*)_MSCSERVER/<class name=\"\1/ig;
s/<class name=\"(.*)_ENODEB\"/<class name=\"\1\"/ig;
s/<class name=\"(.*)3900/<class name=\"\1/ig;
" /mediation/data/cm/huawei/raw/gexport/*.xml || true
        """,
        dag=dag
    )

    parse_huawei_gexport_cm_files = BashOperator(
      task_id='parse_huawei_gexport_cm_files',
      bash_command='java -jar /mediation/bin/boda-huaweicmobjectparser.jar -i /mediation/data/cm/huawei/raw/gexport -o /mediation/data/cm/huawei/parsed/gexport -c /mediation/conf/cm/huawei_gexport_parser.cfg',
      dag=dag)

    import_nbi_csv = BashOperator(
        task_id='import_huawei_gexport_parsed_csv',
        bash_command='python /mediation/bin/load_cm_data_into_db.py huawei_gexport /mediation/data/cm/huawei/parsed/gexport',
        dag=dag)

    t_run_huawei_gexport_insert_queries = BashOperator(
        task_id='run_huawei_gexport_insert_queries',
        bash_command='python /mediation/bin/run_cm_load_insert_queries.py huawei_gexport',
        dag=dag)


    # Clear 4G CM data tables
    def clear_huawei_gexport_cm_tables():
        pass

    t50 = PythonOperator(
        task_id='clear_huawei_gexport_cm_tables',
        python_callable=clear_huawei_gexport_cm_tables,
        dag=dag)

    dag.set_dependency('clean_gexport_mo_names', 'parse_huawei_gexport_cm_files')
    dag.set_dependency('parse_huawei_gexport_cm_files', 'clear_huawei_gexport_cm_tables')
    dag.set_dependency('clear_huawei_gexport_cm_tables', 'import_huawei_gexport_parsed_csv')
    dag.set_dependency('import_huawei_gexport_parsed_csv', 'run_huawei_gexport_insert_queries')

    return dag