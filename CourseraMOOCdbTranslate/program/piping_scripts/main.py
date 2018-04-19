from utilities import db
from utilities import sanity_checks, logger
from observations import *
from resources import *
from users import *
from collaborations import *
from tests import *
from post_conversion.anonymization import *
from post_conversion.oe_durations_and_session_starts import * 
from datetime import datetime
import warnings
import phpserialize



def main(vars):


 
   # Sanity checks

   # --------------

   sanity_checks.KeyExistsValueNonEmpty(vars['source'], ['platform_format'])

   sanity_checks.KeyExistsValueNonEmpty(vars['core'], ['host', 'port'])

   sanity_checks.KeyExists(vars['core'], ['user', 'password'])

   sanity_checks.KeyExistsValueNonEmpty(vars['target'], ['host', 'port', 'db'])

   sanity_checks.KeyExists(vars['target'], ['user', 'password'])

   
  
   platform_format = vars['source']['platform_format']

   if platform_format in ['coursera_1', 'coursera_2']:

       sanity_checks.KeyExists(vars['source'], ['user', 'password'])

       sanity_checks.KeyExistsValueNonEmpty(vars['source'], ['host', 'port', 'hash_mapping_db', 'general_db', 'forum_db', 'course_url_id'])
 
       if platform_format == 'coursera_1':
            sanity_checks.KeyExistsValueNonEmpty(vars['source'], ['course_id'])
    elif platform_format == 'novoed':
        sanity_checks.KeyExistsValueNonEmpty(vars['source'], ['db'])
    elif platform_format == 'openedx':
        sanity_checks.KeyExists(vars['source'], ['lms_user', 'cms_user', 'lms_password', 'cms_password', 'tracklog_password', 'tracklog_password'])
        sanity_checks.KeyExistsValueNonEmpty(vars['source'], ['lms_host', 'lms_port', 'lms_db', 'course_org', 'course_id_1', 'course_id_2'])
        sanity_checks.KeyExistsValueNonEmpty(vars['source'], ['tracklog_host', 'tracklog_port', 'tracklog_db'])
        sanity_checks.KeyExistsValueNonEmpty(vars['source'], ['cms_host', 'cms_port', 'modulestore_db', 'forum_contents_db', 'forum_subscriptions_db', 'forum_users_db'])
    
    # ---------------------------------------------------------------------------------------------------------------------------
    
    
    


    # Internal settings
    # ------------------
    vars['core']['db'] = 'moocdb_core'
    vars['target']['clean_db'] = 'moocdb_clean'
    vars['options']['operations'] = []
    
    start_dt = datetime.now()
    vars['task_id'] = "{0:04d}{1:02d}{2:02d}{3:02d}{4:02d}{5:02d}-{6}".format(start_dt.year, start_dt.month, start_dt.day, start_dt.hour, start_dt.minute, start_dt.second, vars['target']['db'])
    vars['task_static_id'] = vars['target']['db']
    
    vars['logger'] = logger
    vars['log_file'] = vars['options']['log_path'] + "/{}.log".format(vars['task_id'])
    
    vars['logger'].Log(vars, "Starting transformation to {} on {}".format(vars['target']['db'], start_dt.isoformat(sep=" ")))
    # ---------------------------------------------------------------------------------------------------------------------------
    
    
    if len(vars['options']['operations']) == 0 or 'conversion' in vars['options']['operations']:
        
        # DB setup
        # ---------
        (core_con, core_cur) = db.connect(vars['core']['host'], vars['core']['user'], vars['core']['password'], vars['core']['port'], vars['core']['db'])
        with warnings.catch_warnings():
            #warnings.filterwarnings('ignore', 'unknown table')
            warnings.simplefilter('ignore')
            db.Execute(core_cur, "DROP DATABASE IF EXISTS `{}`".format(vars['target']['db']))
            db.Execute(core_cur, "CREATE DATABASE `{}`".format(vars['target']['db']))

        
        
        (target_con, target_cur) = db.connect(vars['target']['host'], vars['target']['user'], vars['target']['password'], vars['target']['port'], vars['target']['db'])
        db.CloneDB(target_cur, vars['target']['clean_db'], vars['target']['db'])
        db.CloneTableContents(target_cur, vars['core']['db'], vars['target']['db'], ['collaboration_types', 'observed_event_types', 'problem_types', 'resource_types', 'user_types'])
    
    
        # Platform-independent setup
        import queries.common as common_queries
        vars['common_queries'] = common_queries
        
        # Platform-specific setup
        if 'coursera' in platform_format:
            import queries.coursera as q
        elif 'novoed' in platform_format:
            import queries.novoed as q
        elif 'openedx' in platform_format:
            import queries.openedx as q
        
        vars['queries'] = q
        
        # Platforms may need to add certain specific vars needed by their queries (Ex: Coursera -> hash map and anonymization keys).
        # The function below allows platforms to add their own elements to 'vars'
        vars = vars['queries'].AddPlatformSpecificVars(vars)
        
        # Conversion
        # -----------
                
        vars["logger"].Log(vars, "Transforming user data ...")
        vars['id_maps'] = {}
        vars['id_maps']['users'] = TransformUserData(vars)
        
        vars["logger"].Log(vars, "Transforming resource data ...")
        resource_id_maps = TransformResourceData(vars)
        for k in resource_id_maps.keys(): vars['id_maps'][k] = resource_id_maps[k]

        vars["logger"].Log(vars, "Transforming collaboration data ...")
        collaboration_id_maps = TransformCollaborationData(vars)
        for k in collaboration_id_maps.keys(): vars['id_maps'][k] = collaboration_id_maps[k]

        
        vars["logger"].Log(vars, "Transforming test data ...")
        test_id_maps = TransformTestData(vars)
        for k in test_id_maps.keys(): vars['id_maps'][k] = test_id_maps[k]
        
        vars["logger"].Log(vars, "Transforming observations data ...")
        TransformObservationData(vars)
        
    # ---------------------------------------------------------------------------------------------------------------------------
    
    
    
    
    # ---------------------------------------------------------------------------------------------------------------------------
    
    # Post-conversion Operations
    # --------------------------
    #if len(vars['options']['operations']) == 0 or 'oe_durations_and_session_starts' in vars['options']['operations']:
    #    vars["logger"].Log(vars, "Adding observed event durations and session delimiters ...")
    #    AddOEDurationsAndSessionStarts(vars)
    
    
    # Finalizations
    # ---------------
    completion_dt = datetime.now()
    dur = (completion_dt - start_dt).seconds
    hours = dur/3600
    minutes = (dur - 3600*hours)/60
    vars['logger'].Log(vars, "Completed on {0}. Duration: {1:02d} hrs, {2:02d} minutes".format(completion_dt.isoformat(sep=" "), hours, minutes))

