# Install and start **Vitrage** service in devstack
#
# To enable vitrage in devstack add an entry to local.conf that
# looks like
#
# [[local|localrc]]
# enable_plugin vitrage git://git.openstack.org/openstack/vitrage
#
# By default all vitrage services are started (see
# devstack/settings).
#

# Defaults
# --------
GITDIR["python-vitrageclient"]=$DEST/python-vitrageclient
GITREPO["python-vitrageclient"]=${VITRAGECLIENT_REPO:-${GIT_BASE}/openstack/python-vitrageclient.git}
GITBRANCH["python-vitrageclient"]=${VITRAGECLIENT_BRANCH:-master}

# Support potential entry-points console scripts in VENV or not
if [[ ${USE_VENV} = True ]]; then
    PROJECT_VENV["vitrage"]=${VITRAGE_DIR}.venv
    VITRAGE_BIN_DIR=${PROJECT_VENV["vitrage"]}/bin
else
    VITRAGE_BIN_DIR=$(get_python_exec_prefix)
fi

# Test if any Vitrage services are enabled
# is_vitrage_enabled
function is_vitrage_enabled {
    [[ ,${ENABLED_SERVICES} =~ ,"vitrage-" ]] && return 0
    return 1
}

function vitrage_service_url {
    echo "$VITRAGE_SERVICE_PROTOCOL://$VITRAGE_SERVICE_HOST:$VITRAGE_SERVICE_PORT"
}


# Configure mod_wsgi
function _vitrage_config_apache_wsgi {
    sudo mkdir -p $VITRAGE_WSGI_DIR

    local vitrage_apache_conf=$(apache_site_config_for vitrage)
    local apache_version=$(get_apache_version)
    local venv_path=""

    # Copy proxy vhost and wsgi file
    sudo cp $VITRAGE_DIR/vitrage/api/app.wsgi $VITRAGE_WSGI_DIR/app

    if [[ ${USE_VENV} = True ]]; then
        venv_path="python-path=${PROJECT_VENV["vitrage"]}/lib/$(python_version)/site-packages"
    fi

    sudo cp $VITRAGE_DIR/devstack/apache-vitrage.template $vitrage_apache_conf

    sudo sed -e "
        s|%PORT%|$VITRAGE_SERVICE_PORT|g;
        s|%APACHE_NAME%|$APACHE_NAME|g;
        s|%WSGIAPP%|$VITRAGE_WSGI_DIR/app|g;
        s|%USER%|$STACK_USER|g;
        s|%APIWORKERS%|$API_WORKERS|g;
        s|%VIRTUALENV%|$venv_path|g
    " -i $vitrage_apache_conf
}


# Create vitrage related accounts in Keystone
function _vitrage_create_accounts {
    if is_service_enabled vitrage-api; then

        create_service_user "vitrage" "admin"

        local vitrage_service=$(get_or_create_service "vitrage" \
            "rca" "Root Cause Analysis Service")
        get_or_create_endpoint $vitrage_service \
            "$REGION_NAME" \
            "$(vitrage_service_url)" \
            "$(vitrage_service_url)" \
            "$(vitrage_service_url)"
    fi
}

# Activities to do before vitrage has been installed.
function preinstall_vitrage {
    # Nothing for now
    :
}

# Remove WSGI files, disable and remove Apache vhost file
function _vitrage_cleanup_apache_wsgi {
    sudo rm -f $VITRAGE_WSGI_DIR/*
    sudo rm -f $(apache_site_config_for vitrage)
}

# cleanup_vitrage() - Remove residual data files, anything left over
# from previous runs that a clean run would need to clean up
function cleanup_vitrage {
    if [ "$VITRAGE_USE_MOD_WSGI" == "True" ]; then
        _vitrage_cleanup_apache_wsgi
    fi
}

function disable_vitrage_datasource {

    local enabled_datasources=",${VITRAGE_DEFAULT_DATASOURCES},"
    local datasource
    for datasource in $@; do
            enabled_datasources=${enabled_datasources//,$datasource,/,}
    done
    VITRAGE_DEFAULT_DATASOURCES=$(_cleanup_service_list "$enabled_datasources")

}

# Configure Vitrage
function configure_vitrage {
    iniset_rpc_backend vitrage $VITRAGE_CONF

    iniset $VITRAGE_CONF DEFAULT debug "$ENABLE_DEBUG_LOG_LEVEL"

    # Install the policy file for the API server
    cp $VITRAGE_DIR/etc/vitrage/policy.json $VITRAGE_CONF_DIR
    iniset $VITRAGE_CONF oslo_policy policy_file $VITRAGE_CONF_DIR/policy.json

    cp $VITRAGE_DIR/etc/vitrage/api-paste.ini $VITRAGE_CONF_DIR

    # Service credentials - openstack clients using keystone
    iniset $VITRAGE_CONF service_credentials auth_type password
    iniset $VITRAGE_CONF service_credentials username admin
    iniset $VITRAGE_CONF service_credentials user_domain_id default
    iniset $VITRAGE_CONF service_credentials project_domain_id default
    iniset $VITRAGE_CONF service_credentials password $ADMIN_PASSWORD
    iniset $VITRAGE_CONF service_credentials project_name admin
    iniset $VITRAGE_CONF service_credentials region_name $REGION_NAME
    iniset $VITRAGE_CONF service_credentials auth_url $KEYSTONE_SERVICE_URI

    # remove neutron vitrage datasource if neutron datasource not installed
    if ! is_service_enabled neutron; then
        disable_vitrage_datasource neutron.network neutron.port
    fi

    # remove aodh vitrage datasource if aodh datasource not installed
    if ! is_service_enabled aodh; then
        disable_vitrage_datasource aodh
    fi

    # remove nagios vitrage datasource if nagios datasource not installed
    if [ "$VITRAGE_USE_NAGIOS" == "False" ]; then
        disable_vitrage_datasource nagios
    fi

    # add default datasources
    iniset $VITRAGE_CONF datasources types $VITRAGE_DEFAULT_DATASOURCES

    # copy the mock sample files
    cp $VITRAGE_DIR/etc/vitrage/*.sample.json $VITRAGE_CONF_DIR

    # create some folders
    mkdir -p $VITRAGE_CONF_DIR/datasources_values
    mkdir -p $VITRAGE_CONF_DIR/static_datasources
    mkdir -p $VITRAGE_CONF_DIR/templates

    # copy datasources
    cp $VITRAGE_DIR/etc/vitrage/datasources_values/*.yaml $VITRAGE_CONF_DIR/datasources_values


    configure_auth_token_middleware $VITRAGE_CONF vitrage $VITRAGE_AUTH_CACHE_DIR

    if [ "$VITRAGE_USE_MOD_WSGI" == "True" ]; then
        iniset $VITRAGE_CONF api pecan_debug "False"
        _vitrage_config_apache_wsgi
    fi

}

# init_vitrage() - Initialize etc.
function init_vitrage {
    # Get vitrage keystone settings in place
    _vitrage_create_accounts
    # Create cache dir
    sudo install -d -o $STACK_USER $VITRAGE_AUTH_CACHE_DIR
    rm -f $VITRAGE_AUTH_CACHE_DIR/*

}

# Install Vitrage.
function install_vitrage {
    install_vitrageclient
    setup_develop "$VITRAGE_DIR"
    sudo install -d -o $STACK_USER -m 755 $VITRAGE_CONF_DIR $VITRAGE_API_LOG_DIR
}

# install_vitrageclient()
function install_vitrageclient {
    if use_library_from_git "python-vitrageclient"; then
        git_clone_by_name "python-vitrageclient"
        setup_dev_lib "python-vitrageclient"
        sudo install -D -m 0644 -o $STACK_USER {${GITDIR["python-vitrageclient"]}/tools/,/etc/bash_completion.d/}vitrage.bash_completion
    else
        pip_install_gr python-vitrageclient
    fi
}

# start_vitrage() - Start running processes, including screen
function start_vitrage {
    if [[ "$VITRAGE_USE_MOD_WSGI" == "False" ]]; then
        run_process vitrage-api "$VITRAGE_BIN_DIR/vitrage-api -d -v --log-dir=$VITRAGE_API_LOG_DIR --config-file $VITRAGE_CONF"
    else
        enable_apache_site vitrage
        restart_apache_server
        tail_log vitrage /var/log/$APACHE_NAME/vitrage.log
        tail_log vitrage-api /var/log/$APACHE_NAME/vitrage_access.log
    fi

    # Only die on API if it was actually intended to be turned on
    if is_service_enabled vitrage-api; then
        echo "Waiting for vitrage-api to start..."
        if ! wait_for_service $SERVICE_TIMEOUT $(vitrage_service_url)/v1/; then
            die $LINENO "vitrage-api did not start"
        fi
    fi

    run_process vitrage-graph "$VITRAGE_BIN_DIR/vitrage-graph --config-file $VITRAGE_CONF"
    run_process vitrage-notifier "$VITRAGE_BIN_DIR/vitrage-notifier --config-file $VITRAGE_CONF"
}

# stop_vitrage() - Stop running processes
function stop_vitrage {
    if [ "$VITRAGE_USE_MOD_WSGI" == "True" ]; then
        disable_apache_site vitrage
        restart_apache_server
    fi
    # Kill the vitrage screen windows
    for serv in vitrage-api vitrage-graph vitrage-notifier; do
        stop_process $serv
    done
}

# This is the main for plugin.sh
if is_service_enabled vitrage; then
    if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then
        # Set up other services
        echo_summary "Configuring system services for Vitrage"
        preinstall_vitrage
    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing Vitrage"
        # Use stack_install_service here to account for virtualenv
        stack_install_service vitrage
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        echo_summary "Configuring Vitrage"
        configure_vitrage
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        echo_summary "Initializing Vitrage"
        # Tidy base for vitrage
        init_vitrage
        # Start the services
        start_vitrage
    fi

    if [[ "$1" == "unstack" ]]; then
        echo_summary "Shutting Down Vitrage"
        stop_vitrage
    fi

    if [[ "$1" == "clean" ]]; then
        echo_summary "Cleaning Vitrage"
        cleanup_vitrage
    fi
fi
