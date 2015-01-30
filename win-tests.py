#
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
#
"""
Driver for running the tests on Windows.

For a list of options, run this script with the --help option.
"""

# $HeadURL: http://svn.apache.org/repos/asf/subversion/trunk/win-tests.py $
# $LastChangedRevision: 1643078 $

import os, sys, subprocess
import filecmp
import shutil
import traceback
try:
  # Python >=3.0
  import configparser
except ImportError:
  # Python <3.0
  import ConfigParser as configparser
import string
import random

import getopt
try:
    my_getopt = getopt.gnu_getopt
except AttributeError:
    my_getopt = getopt.getopt

def _usage_exit():
  "print usage, exit the script"

  print("Driver for running the tests on Windows.")
  print("Usage: python win-tests.py [option] [test-path]")
  print("")
  print("Valid options:")
  print("  -r, --release          : test the Release configuration")
  print("  -d, --debug            : test the Debug configuration (default)")
  print("  --bin=PATH             : use the svn binaries installed in PATH")
  print("  -u URL, --url=URL      : run ra_dav or ra_svn tests against URL;")
  print("                           will start svnserve for ra_svn tests")
  print("  -v, --verbose          : talk more")
  print("  -q, --quiet            : talk less")
  print("  -f, --fs-type=type     : filesystem type to use (fsfs is default)")
  print("  -c, --cleanup          : cleanup after running a test")
  print("  -t, --test=TEST        : Run the TEST test (all is default); use")
  print("                           TEST#n to run a particular test number,")
  print("                           multiples also accepted e.g. '2,4-7'")
  print("  --log-level=LEVEL      : Set log level to LEVEL (E.g. DEBUG)")
  print("  --log-to-stdout        : Write log results to stdout")

  print("  --svnserve-args=list   : comma-separated list of arguments for")
  print("                           svnserve")
  print("                           default is '-d,-r,<test-path-root>'")
  print("  --asp.net-hack         : use '_svn' instead of '.svn' for the admin")
  print("                           dir name")
  print("  --httpd-dir            : location where Apache HTTPD is installed")
  print("  --httpd-port           : port for Apache HTTPD; random port number")
  print("                           will be used, if not specified")
  print("  --httpd-daemon         : Run Apache httpd as daemon")
  print("  --httpd-service        : Run Apache httpd as Windows service (default)")
  print("  --httpd-no-log         : Disable httpd logging")
  print("  --http-short-circuit   : Use SVNPathAuthz short_circuit on HTTP server")
  print("  --disable-http-v2      : Do not advertise support for HTTPv2 on server")
  print("  --disable-bulk-updates : Disable bulk updates on HTTP server")
  print("  --ssl-cert             : Path to SSL server certificate to trust.")
  print("  --javahl               : Run the javahl tests instead of the normal tests")
  print("  --swig=language        : Run the swig perl/python/ruby tests instead of")
  print("                           the normal tests")
  print("  --list                 : print test doc strings only")
  print("  --milestone-filter=RE  : RE is a regular expression pattern that (when")
  print("                           used with --list) limits the tests listed to")
  print("                           those with an associated issue in the tracker")
  print("                           which has a target milestone that matches RE.")
  print("  --mode-filter=TYPE     : limit tests to expected TYPE = XFAIL, SKIP, PASS,")
  print("                           or 'ALL' (default)")
  print("  --enable-sasl          : enable Cyrus SASL authentication for")
  print("                           svnserve")
  print("  -p, --parallel         : run multiple tests in parallel")
  print("  --server-minor-version : the minor version of the server being")
  print("                           tested")
  print("  --config-file          : Configuration file for tests")
  print("  --fsfs-sharding        : Specify shard size (for fsfs)")
  print("  --fsfs-packing         : Run 'svnadmin pack' automatically")

  sys.exit(0)

CMDLINE_TEST_SCRIPT_PATH = 'subversion/tests/cmdline/'
CMDLINE_TEST_SCRIPT_NATIVE_PATH = CMDLINE_TEST_SCRIPT_PATH.replace('/', os.sep)

sys.path.insert(0, os.path.join('build', 'generator'))
sys.path.insert(1, 'build')

import gen_win_dependencies
import gen_base
version_header = os.path.join('subversion', 'include', 'svn_version.h')
cp = configparser.ConfigParser()
cp.read('gen-make.opts')
gen_obj = gen_win_dependencies.GenDependenciesBase('build.conf', version_header,
                                                   cp.items('options'))
opts, args = my_getopt(sys.argv[1:], 'hrdvqct:pu:f:',
                       ['release', 'debug', 'verbose', 'quiet', 'cleanup',
                        'test=', 'url=', 'svnserve-args=', 'fs-type=', 'asp.net-hack',
                        'httpd-dir=', 'httpd-port=', 'httpd-daemon',
                        'httpd-server', 'http-short-circuit', 'httpd-no-log',
                        'disable-http-v2', 'disable-bulk-updates', 'help',
                        'fsfs-packing', 'fsfs-sharding=', 'javahl', 'swig=',
                        'list', 'enable-sasl', 'bin=', 'parallel',
                        'config-file=', 'server-minor-version=', 'log-level=',
                        'log-to-stdout', 'mode-filter=', 'milestone-filter=',
                        'ssl-cert='])
if len(args) > 1:
  print('Warning: non-option arguments after the first one will be ignored')

# Interpret the options and set parameters
base_url, fs_type, verbose, quiet, cleanup = None, None, None, None, None
repo_loc = 'local repository.'
objdir = 'Debug'
log = 'tests.log'
faillog = 'fails.log'
run_svnserve = None
svnserve_args = None
run_httpd = None
httpd_port = None
httpd_service = None
httpd_no_log = None
http_short_circuit = False
advertise_httpv2 = True
http_bulk_updates = True
list_tests = None
milestone_filter = None
test_javahl = None
test_swig = None
enable_sasl = None
svn_bin = None
parallel = None
fsfs_sharding = None
fsfs_packing = None
server_minor_version = None
config_file = None
log_to_stdout = None
mode_filter=None
tests_to_run = []
log_level = None
ssl_cert = None

for opt, val in opts:
  if opt in ('-h', '--help'):
    _usage_exit()
  elif opt in ('-u', '--url'):
    base_url = val
  elif opt in ('-f', '--fs-type'):
    fs_type = val
  elif opt in ('-v', '--verbose'):
    verbose = 1
  elif opt in ('-q', '--quiet'):
    quiet = 1
  elif opt in ('-c', '--cleanup'):
    cleanup = 1
  elif opt in ('-t', '--test'):
    tests_to_run.append(val)
  elif opt in ['-r', '--release']:
    objdir = 'Release'
  elif opt in ['-d', '--debug']:
    objdir = 'Debug'
  elif opt == '--svnserve-args':
    svnserve_args = val.split(',')
    run_svnserve = 1
  elif opt == '--asp.net-hack':
    os.environ['SVN_ASP_DOT_NET_HACK'] = opt
  elif opt == '--httpd-dir':
    abs_httpd_dir = os.path.abspath(val)
    run_httpd = 1
  elif opt == '--httpd-port':
    httpd_port = int(val)
  elif opt == '--httpd-daemon':
    httpd_service = 0
  elif opt == '--httpd-service':
    httpd_service = 1
  elif opt == '--httpd-no-log':
    httpd_no_log = 1
  elif opt == '--http-short-circuit':
    http_short_circuit = True
  elif opt == '--disable-http-v2':
    advertise_httpv2 = False
  elif opt == '--disable-bulk-updates':
    http_bulk_updates = False
  elif opt == '--fsfs-sharding':
    fsfs_sharding = int(val)
  elif opt == '--fsfs-packing':
    fsfs_packing = 1
  elif opt == '--javahl':
    test_javahl = 1
  elif opt == '--swig':
    if val not in ['perl', 'python', 'ruby']:
      sys.stderr.write('Running \'%s\' swig tests not supported (yet).\n' 
                        % (val,))
    test_swig = val
  elif opt == '--list':
    list_tests = 1
  elif opt == '--milestone-filter':
    milestone_filter = val
  elif opt == '--mode-filter':
    mode_filter = val
  elif opt == '--enable-sasl':
    enable_sasl = 1
    base_url = "svn://localhost/"
  elif opt == '--server-minor-version':
    server_minor_version = val
  elif opt == '--bin':
    svn_bin = val
  elif opt in ('-p', '--parallel'):
    parallel = 1
  elif opt in ('--config-file'):
    config_file = val
  elif opt == '--log-to-stdout':
    log_to_stdout = 1
  elif opt == '--log-level':
    log_level = val
  elif opt == '--ssl-cert':
    ssl_cert = val

# Calculate the source and test directory names
abs_srcdir = os.path.abspath("")
abs_objdir = os.path.join(abs_srcdir, objdir)
if len(args) == 0:
  abs_builddir = abs_objdir
  create_dirs = 0
else:
  abs_builddir = os.path.abspath(args[0])
  create_dirs = 1

# Default to fsfs explicitly
if not fs_type:
  fs_type = 'fsfs'

if fs_type == 'bdb':
  all_tests = gen_obj.test_progs + gen_obj.bdb_test_progs \
            + gen_obj.scripts + gen_obj.bdb_scripts
else:
  all_tests = gen_obj.test_progs + gen_obj.scripts            

client_tests = [x for x in all_tests if x.startswith(CMDLINE_TEST_SCRIPT_PATH)]

if run_httpd:
  if not httpd_port:
    httpd_port = random.randrange(1024, 30000)
  if not base_url:
    base_url = 'http://localhost:' + str(httpd_port)

if base_url:
  repo_loc = 'remote repository ' + base_url + '.'
  if base_url[:4] == 'http':
    log = 'dav-tests.log'
    faillog = 'dav-fails.log'
  elif base_url[:3] == 'svn':
    log = 'svn-tests.log'
    faillog = 'svn-fails.log'
    run_svnserve = 1
  else:
    # Don't know this scheme, but who're we to judge whether it's
    # correct or not?
    log = 'url-tests.log'
    faillog = 'url-fails.log'

# Have to move the executables where the tests expect them to be
copied_execs = []   # Store copied exec files to avoid the final dir scan

def create_target_dir(dirname):
  tgt_dir = os.path.join(abs_builddir, dirname)
  if not os.path.exists(tgt_dir):
    if verbose:
      print("mkdir: %s" % tgt_dir)
    os.makedirs(tgt_dir)

def copy_changed_file(src, tgt=None, to_dir=None, cleanup=True):
  if not os.path.isfile(src):
    print('Could not find ' + src)
    sys.exit(1)

  if to_dir and not tgt:
    tgt = os.path.join(to_dir, os.path.basename(src))
  elif not tgt or (tgt and to_dir):
    raise RuntimeError("Using 'tgt' *or* 'to_dir' is required" % (tgt,))
  elif tgt and os.path.isdir(tgt):
    raise RuntimeError("'%s' is a directory. Use to_dir=" % (tgt,))

  if os.path.exists(tgt):
    assert os.path.isfile(tgt)
    if filecmp.cmp(src, tgt):
      if verbose:
        print("same: %s" % src)
        print(" and: %s" % tgt)
      return 0
  if verbose:
    print("copy: %s" % src)
    print("  to: %s" % tgt)
  shutil.copy(src, tgt)

  if cleanup:
    copied_execs.append(tgt)

def locate_libs():
  "Move DLLs to a known location and set env vars"

  debug = (objdir == 'Debug')
  
  for lib in gen_obj._libraries.values():

    if debug:
      name, dir = lib.debug_dll_name, lib.debug_dll_dir
    else:
      name, dir = lib.dll_name, lib.dll_dir
      
    if name and dir:
      src = os.path.join(dir, name)
      if os.path.exists(src):
        copy_changed_file(src, to_dir=abs_builddir, cleanup=False)

    for name in lib.extra_bin:
      src = os.path.join(dir, name)
      copy_changed_file(src, to_dir=abs_builddir)


  # Copy the Subversion library DLLs
  for i in gen_obj.graph.get_all_sources(gen_base.DT_INSTALL):
    if isinstance(i, gen_base.TargetLib) and i.msvc_export:
      src = os.path.join(abs_objdir, i.filename)
      if os.path.isfile(src):
        copy_changed_file(src, to_dir=abs_builddir,
                          cleanup=False)

  # Copy the Apache modules
  if run_httpd and cp.has_option('options', '--with-httpd'):
    mod_dav_svn_path = os.path.join(abs_objdir, 'subversion',
                                    'mod_dav_svn', 'mod_dav_svn.so')
    mod_authz_svn_path = os.path.join(abs_objdir, 'subversion',
                                      'mod_authz_svn', 'mod_authz_svn.so')
    mod_dontdothat_path = os.path.join(abs_objdir, 'tools', 'server-side',
                                        'mod_dontdothat', 'mod_dontdothat.so')

    copy_changed_file(mod_dav_svn_path, to_dir=abs_builddir, cleanup=False)
    copy_changed_file(mod_authz_svn_path, to_dir=abs_builddir, cleanup=False)
    copy_changed_file(mod_dontdothat_path, to_dir=abs_builddir, cleanup=False)

  os.environ['PATH'] = abs_builddir + os.pathsep + os.environ['PATH']

def fix_case(path):
    path = os.path.normpath(path)
    parts = path.split(os.path.sep)
    drive = parts[0].upper()
    parts = parts[1:]
    path = drive + os.path.sep
    for part in parts:
        dirs = os.listdir(path)
        for dir in dirs:
            if dir.lower() == part.lower():
                path = os.path.join(path, dir)
                break
    return path

class Svnserve:
  "Run svnserve for ra_svn tests"
  def __init__(self, svnserve_args, objdir, abs_objdir, abs_builddir):
    self.args = svnserve_args
    self.name = 'svnserve.exe'
    self.kind = objdir
    self.path = os.path.join(abs_objdir,
                             'subversion', 'svnserve', self.name)
    self.root = os.path.join(abs_builddir, CMDLINE_TEST_SCRIPT_NATIVE_PATH)
    self.proc = None

  def __del__(self):
    "Stop svnserve when the object is deleted"
    self.stop()

  def _quote(self, arg):
    if ' ' in arg:
      return '"' + arg + '"'
    else:
      return arg

  def start(self):
    if not self.args:
      args = [self.name, '-d', '-r', self.root]
    else:
      args = [self.name] + self.args
    print('Starting %s %s' % (self.kind, self.name))

    self.proc = subprocess.Popen([self.path] + args[1:])

  def stop(self):
    if self.proc is not None:
      try:
        print('Stopping %s' % self.name)
        self.proc.poll();
        if self.proc.returncode is None:
          self.proc.kill();
        return
      except AttributeError:
        pass
    print('Svnserve.stop not implemented')

class Httpd:
  "Run httpd for DAV tests"
  def __init__(self, abs_httpd_dir, abs_objdir, abs_builddir, httpd_port,
               service, no_log, httpv2, short_circuit, bulk_updates):
    self.name = 'apache.exe'
    self.httpd_port = httpd_port
    self.httpd_dir = abs_httpd_dir

    if httpv2:
      self.httpv2_option = 'on'
    else:
      self.httpv2_option = 'off'

    if bulk_updates:
      self.bulkupdates_option = 'on'
    else:
      self.bulkupdates_option = 'off'

    self.service = service
    self.proc = None
    self.path = os.path.join(self.httpd_dir, 'bin', self.name)

    if short_circuit:
      self.path_authz_option = 'short_circuit'
    else:
      self.path_authz_option = 'on'

    if not os.path.exists(self.path):
      self.name = 'httpd.exe'
      self.path = os.path.join(self.httpd_dir, 'bin', self.name)
      if not os.path.exists(self.path):
        raise RuntimeError("Could not find a valid httpd binary!")

    self.root_dir = os.path.join(CMDLINE_TEST_SCRIPT_NATIVE_PATH, 'httpd')
    self.root = os.path.join(abs_builddir, self.root_dir)
    self.authz_file = os.path.join(abs_builddir,
                                   CMDLINE_TEST_SCRIPT_NATIVE_PATH,
                                   'svn-test-work', 'authz')
    self.dontdothat_file = os.path.join(abs_builddir,
                                         CMDLINE_TEST_SCRIPT_NATIVE_PATH,
                                         'svn-test-work', 'dontdothat')
    self.httpd_config = os.path.join(self.root, 'httpd.conf')
    self.httpd_users = os.path.join(self.root, 'users')
    self.httpd_mime_types = os.path.join(self.root, 'mime.types')
    self.abs_builddir = abs_builddir
    self.abs_objdir = abs_objdir
    self.service_name = 'svn-test-httpd-' + str(httpd_port)

    if self.service:
      self.httpd_args = [self.name, '-n', self._quote(self.service_name),
                         '-f', self._quote(self.httpd_config)]
    else:
      self.httpd_args = [self.name, '-f', self._quote(self.httpd_config)]

    create_target_dir(self.root_dir)

    self._create_users_file()
    self._create_mime_types_file()
    self._create_dontdothat_file()

    # Obtain version.
    version_vals = gen_obj._libraries['httpd'].version.split('.')
    self.httpd_ver = float('%s.%s' % (version_vals[0], version_vals[1]))

    # Create httpd config file
    fp = open(self.httpd_config, 'w')

    # Limit the number of threads (default = 64)
    fp.write('<IfModule mpm_winnt.c>\n')
    fp.write('ThreadsPerChild 16\n')
    fp.write('</IfModule>\n')

    # Global Environment
    fp.write('ServerRoot   ' + self._quote(self.root) + '\n')
    fp.write('DocumentRoot ' + self._quote(self.root) + '\n')
    fp.write('ServerName   localhost\n')
    fp.write('PidFile      pid\n')
    fp.write('ErrorLog     log\n')
    fp.write('Listen       ' + str(self.httpd_port) + '\n')

    if not no_log:
      fp.write('LogFormat    "%h %l %u %t \\"%r\\" %>s %b" common\n')
      fp.write('Customlog    log common\n')
      fp.write('LogLevel     Debug\n')
    else:
      fp.write('LogLevel     Crit\n')

    # Write LoadModule for minimal system module
    fp.write(self._sys_module('dav_module', 'mod_dav.so'))
    if self.httpd_ver >= 2.3:
      fp.write(self._sys_module('access_compat_module', 'mod_access_compat.so'))
      fp.write(self._sys_module('authz_core_module', 'mod_authz_core.so'))
      fp.write(self._sys_module('authz_user_module', 'mod_authz_user.so'))
      fp.write(self._sys_module('authn_core_module', 'mod_authn_core.so'))
    if self.httpd_ver >= 2.2:
      fp.write(self._sys_module('auth_basic_module', 'mod_auth_basic.so'))
      fp.write(self._sys_module('authn_file_module', 'mod_authn_file.so'))
    else:
      fp.write(self._sys_module('auth_module', 'mod_auth.so'))
    fp.write(self._sys_module('alias_module', 'mod_alias.so'))
    fp.write(self._sys_module('mime_module', 'mod_mime.so'))
    fp.write(self._sys_module('log_config_module', 'mod_log_config.so'))

    # Write LoadModule for Subversion modules
    fp.write(self._svn_module('dav_svn_module', 'mod_dav_svn.so'))
    fp.write(self._svn_module('authz_svn_module', 'mod_authz_svn.so'))

    # And for mod_dontdothat
    fp.write(self._svn_module('dontdothat_module', 'mod_dontdothat.so'))

    # Don't handle .htaccess, symlinks, etc.
    fp.write('<Directory />\n')
    fp.write('AllowOverride None\n')
    fp.write('Options None\n')
    fp.write('</Directory>\n\n')

    # Define two locations for repositories
    fp.write(self._svn_repo('repositories'))
    fp.write(self._svn_repo('local_tmp'))

    # And two redirects for the redirect tests
    fp.write('RedirectMatch permanent ^/svn-test-work/repositories/'
             'REDIRECT-PERM-(.*)$ /svn-test-work/repositories/$1\n')
    fp.write('RedirectMatch           ^/svn-test-work/repositories/'
             'REDIRECT-TEMP-(.*)$ /svn-test-work/repositories/$1\n')

    fp.write('TypesConfig     ' + self._quote(self.httpd_mime_types) + '\n')
    fp.write('HostNameLookups Off\n')

    fp.close()

  def __del__(self):
    "Stop httpd when the object is deleted"
    self.stop()

  def _quote(self, arg):
    if ' ' in arg:
      return '"' + arg + '"'
    else:
      return arg

  def _create_users_file(self):
    "Create users file"
    htpasswd = os.path.join(self.httpd_dir, 'bin', 'htpasswd.exe')
    # Create the cheapest to compare password form for our testsuite
    os.spawnv(os.P_WAIT, htpasswd, ['htpasswd.exe', '-bcp', self.httpd_users,
                                    'jrandom', 'rayjandom'])
    os.spawnv(os.P_WAIT, htpasswd, ['htpasswd.exe', '-bp',  self.httpd_users,
                                    'jconstant', 'rayjandom'])

  def _create_mime_types_file(self):
    "Create empty mime.types file"
    fp = open(self.httpd_mime_types, 'w')
    fp.close()

  def _create_dontdothat_file(self):
    "Create empty mime.types file"
    # If the tests have not previously been run or were cleaned
    # up, then 'svn-test-work' does not exist yet.
    parent_dir = os.path.dirname(self.dontdothat_file)
    if not os.path.exists(parent_dir):
      os.makedirs(parent_dir)

    fp = open(self.dontdothat_file, 'w')
    fp.write('[recursive-actions]\n')
    fp.write('/ = deny\n')
    fp.close()

  def _sys_module(self, name, path):
    full_path = os.path.join(self.httpd_dir, 'modules', path)
    return 'LoadModule ' + name + " " + self._quote(full_path) + '\n'

  def _svn_module(self, name, path):
    full_path = os.path.join(self.abs_builddir, path)
    return 'LoadModule ' + name + ' ' + self._quote(full_path) + '\n'

  def _svn_repo(self, name):
    path = os.path.join(self.abs_builddir,
                        CMDLINE_TEST_SCRIPT_NATIVE_PATH,
                        'svn-test-work', name)
    location = '/svn-test-work/' + name
    ddt_location = '/ddt-test-work/' + name
    return \
      '<Location ' + location + '>\n' \
      '  DAV             svn\n' \
      '  SVNParentPath   ' + self._quote(path) + '\n' \
      '  SVNAdvertiseV2Protocol ' + self.httpv2_option + '\n' \
      '  SVNPathAuthz ' + self.path_authz_option + '\n' \
      '  SVNAllowBulkUpdates ' + self.bulkupdates_option + '\n' \
      '  AuthzSVNAccessFile ' + self._quote(self.authz_file) + '\n' \
      '  AuthType        Basic\n' \
      '  AuthName        "Subversion Repository"\n' \
      '  AuthUserFile    ' + self._quote(self.httpd_users) + '\n' \
      '  Require         valid-user\n' \
      '</Location>\n' \
      '<Location ' + ddt_location + '>\n' \
      '  DAV             svn\n' \
      '  SVNParentPath   ' + self._quote(path) + '\n' \
      '  SVNAdvertiseV2Protocol ' + self.httpv2_option + '\n' \
      '  SVNPathAuthz ' + self.path_authz_option + '\n' \
      '  SVNAllowBulkUpdates ' + self.bulkupdates_option + '\n' \
      '  AuthzSVNAccessFile ' + self._quote(self.authz_file) + '\n' \
      '  AuthType        Basic\n' \
      '  AuthName        "Subversion Repository"\n' \
      '  AuthUserFile    ' + self._quote(self.httpd_users) + '\n' \
      '  Require         valid-user\n' \
      '  DontDoThatConfigFile ' + self._quote(self.dontdothat_file) + '\n' \
      '</Location>\n'

  def start(self):
    if self.service:
      self._start_service()
    else:
      self._start_daemon()

  def stop(self):
    if self.service:
      self._stop_service()
    else:
      self._stop_daemon()

  def _start_service(self):
    "Install and start HTTPD service"
    print('Installing service %s' % self.service_name)
    os.spawnv(os.P_WAIT, self.path, self.httpd_args + ['-k', 'install'])
    print('Starting service %s' % self.service_name)
    os.spawnv(os.P_WAIT, self.path, self.httpd_args + ['-k', 'start'])

  def _stop_service(self):
    "Stop and uninstall HTTPD service"
    os.spawnv(os.P_WAIT, self.path, self.httpd_args + ['-k', 'stop'])
    os.spawnv(os.P_WAIT, self.path, self.httpd_args + ['-k', 'uninstall'])

  def _start_daemon(self):
    "Start HTTPD as daemon"
    print('Starting httpd as daemon')
    print(self.httpd_args)
    self.proc = subprocess.Popen([self.path] + self.httpd_args[1:])

  def _stop_daemon(self):
    "Stop the HTTPD daemon"
    if self.proc is not None:
      try:
        print('Stopping %s' % self.name)
        self.proc.poll();
        if self.proc.returncode is None:
          self.proc.kill();
        return
      except AttributeError:
        pass
    print('Httpd.stop_daemon not implemented')

# Move the binaries to the test directory
create_target_dir(abs_builddir)
locate_libs()
if create_dirs:
  for i in gen_obj.graph.get_all_sources(gen_base.DT_INSTALL):
    if isinstance(i, gen_base.TargetExe):
      src = os.path.join(abs_objdir, i.filename)

      if os.path.isfile(src):
        dst = os.path.join(abs_builddir, i.filename)
        create_target_dir(os.path.dirname(dst))
        copy_changed_file(src, dst)

# Create the base directory for Python tests
create_target_dir(CMDLINE_TEST_SCRIPT_NATIVE_PATH)

# Ensure the tests directory is correctly cased
abs_builddir = fix_case(abs_builddir)

daemon = None
# Run the tests

# No need to start any servers if we are only listing the tests.
if not list_tests:
  if run_svnserve:
    daemon = Svnserve(svnserve_args, objdir, abs_objdir, abs_builddir)

  if run_httpd:
    daemon = Httpd(abs_httpd_dir, abs_objdir, abs_builddir, httpd_port,
                   httpd_service, httpd_no_log,
                   advertise_httpv2, http_short_circuit,
                   http_bulk_updates)

  # Start service daemon, if any
  if daemon:
    daemon.start()

# Find the full path and filename of any test that is specified just by
# its base name.
if len(tests_to_run) != 0:
  tests = []
  for t in tests_to_run:
    tns = None
    if '#' in t:
      t, tns = t.split('#')

    test = [x for x in all_tests if x.split('/')[-1] == t]
    if not test and not (t.endswith('-test.exe') or t.endswith('_tests.py')):
      # The lengths of '-test.exe' and of '_tests.py' are both 9.
      test = [x for x in all_tests if x.split('/')[-1][:-9] == t]

    if not test:
      print("Skipping test '%s', test not found." % t)
    elif tns:
      tests.append('%s#%s' % (test[0], tns))
    else:
      tests.extend(test)

  tests_to_run = tests
else:
  tests_to_run = all_tests


if list_tests:
  print('Listing %s configuration on %s' % (objdir, repo_loc))
else:
  print('Testing %s configuration on %s' % (objdir, repo_loc))
sys.path.insert(0, os.path.join(abs_srcdir, 'build'))

if not test_javahl and not test_swig:
  import run_tests
  if log_to_stdout:
    log_file = None
    fail_log_file = None
  else:
    log_file = os.path.join(abs_builddir, log)
    fail_log_file = os.path.join(abs_builddir, faillog)

  th = run_tests.TestHarness(abs_srcdir, abs_builddir,
                             log_file,
                             fail_log_file,
                             base_url, fs_type, 'serf',
                             server_minor_version, not quiet,
                             cleanup, enable_sasl, parallel, config_file,
                             fsfs_sharding, fsfs_packing,
                             list_tests, svn_bin, mode_filter,
                             milestone_filter,
                             set_log_level=log_level, ssl_cert=ssl_cert)
  old_cwd = os.getcwd()
  try:
    os.chdir(abs_builddir)
    failed = th.run(tests_to_run)
  except:
    os.chdir(old_cwd)
    raise
  else:
    os.chdir(old_cwd)
elif test_javahl:
  failed = False

  java_exe = None

  for path in os.environ["PATH"].split(os.pathsep):
    if os.path.isfile(os.path.join(path, 'java.exe')):
      java_exe = os.path.join(path, 'java.exe')
      break

  if not java_exe and 'java_sdk' in gen_obj._libraries:
    jdk = gen_obj._libraries['java_sdk']

    if os.path.isfile(os.path.join(jdk.lib_dir, '../bin/java.exe')):
      java_exe = os.path.join(jdk.lib_dir, '../bin/java.exe')

  if not java_exe:
    print('Java not found. Skipping Java tests')
  else:
    args = (os.path.abspath(java_exe),)
    if (objdir == 'Debug'):
      args = args + ('-Xcheck:jni',)

    args = args + (
            '-Dtest.rootdir=' + os.path.join(abs_builddir, 'javahl'),
            '-Dtest.srcdir=' + os.path.join(abs_srcdir,
                                            'subversion/bindings/javahl'),
            '-Dtest.rooturl=',
            '-Dtest.fstype=' + fs_type ,
            '-Dtest.tests=',
  
            '-Djava.library.path='
                      + os.path.join(abs_objdir,
                                     'subversion/bindings/javahl/native'),
            '-classpath',
            os.path.join(abs_srcdir, 'subversion/bindings/javahl/classes') +';' +
              gen_obj.junit_path
           )

    sys.stderr.flush()
    print('Running org.apache.subversion tests:')
    sys.stdout.flush()

    r = subprocess.call(args + tuple(['org.apache.subversion.javahl.RunTests']))
    sys.stdout.flush()
    sys.stderr.flush()
    if (r != 0):
      print('[Test runner reported failure]')
      failed = True

    print('Running org.tigris.subversion tests:')
    sys.stdout.flush()
    r = subprocess.call(args + tuple(['org.tigris.subversion.javahl.RunTests']))
    sys.stdout.flush()
    sys.stderr.flush()
    if (r != 0):
      print('[Test runner reported failure]')
      failed = True
elif test_swig == 'perl':
  failed = False
  swig_dir = os.path.join(abs_builddir, 'swig')
  swig_pl_dir = os.path.join(swig_dir, 'p5lib')
  swig_pl_svn = os.path.join(swig_pl_dir, 'SVN')
  swig_pl_auto_svn = os.path.join(swig_pl_dir, 'auto', 'SVN')

  create_target_dir(swig_pl_svn)

  for i in gen_obj.graph.get_all_sources(gen_base.DT_INSTALL):
    if isinstance(i, gen_base.TargetSWIG) and i.lang == 'perl':
      mod_dir = os.path.join(swig_pl_auto_svn, '_' + i.name[5:].capitalize())
      create_target_dir(mod_dir)
      copy_changed_file(os.path.join(abs_objdir, i.filename), to_dir=mod_dir)

    elif isinstance(i, gen_base.TargetSWIGLib) and i.lang == 'perl':
      copy_changed_file(os.path.join(abs_objdir, i.filename),
                        to_dir=abs_builddir)

  pm_src = os.path.join(abs_srcdir, 'subversion', 'bindings', 'swig', 'perl',
                        'native')

  tests = []

  for root, dirs, files in os.walk(pm_src):
    for name in files:
      if name.endswith('.pm'):
        fn = os.path.join(root, name)
        copy_changed_file(fn, to_dir=swig_pl_svn)
      elif name.endswith('.t'):
        tests.append(os.path.relpath(os.path.join(root, name), pm_src))

  perl5lib = swig_pl_dir
  if 'PERL5LIB' in os.environ:
    perl5lib += os.pathsep + os.environ['PERL5LIB']

  perl_exe = 'perl.exe'

  print('-- Running Swig Perl tests --')
  sys.stdout.flush()
  old_cwd = os.getcwd()
  try:
    os.chdir(pm_src)

    os.environ['PERL5LIB'] = perl5lib
    os.environ["SVN_DBG_NO_ABORT_ON_ERROR_LEAK"] = 'YES'

    r = subprocess.call([
              perl_exe,
              '-MExtUtils::Command::MM',
              '-e', 'test_harness()'
              ] + tests)
  finally:
    os.chdir(old_cwd)

  if (r != 0):
    print('[Test runner reported failure]')
    failed = True
elif test_swig == 'python':
  failed = False
  swig_dir = os.path.join(abs_builddir, 'swig')
  swig_py_dir = os.path.join(swig_dir, 'pylib')
  swig_py_libsvn = os.path.join(swig_py_dir, 'libsvn')
  swig_py_svn = os.path.join(swig_py_dir, 'svn')

  create_target_dir(swig_py_libsvn)
  create_target_dir(swig_py_svn)

  for i in gen_obj.graph.get_all_sources(gen_base.DT_INSTALL):
    if (isinstance(i, gen_base.TargetSWIG)
        or isinstance(i, gen_base.TargetSWIGLib)) and i.lang == 'python':

      src = os.path.join(abs_objdir, i.filename)
      copy_changed_file(src, to_dir=swig_py_libsvn)

  py_src = os.path.join(abs_srcdir, 'subversion', 'bindings', 'swig', 'python')

  for py_file in os.listdir(py_src):
    if py_file.endswith('.py'):
      copy_changed_file(os.path.join(py_src, py_file),
                        to_dir=swig_py_libsvn)

  py_src_svn = os.path.join(py_src, 'svn')
  for py_file in os.listdir(py_src_svn):
    if py_file.endswith('.py'):
      copy_changed_file(os.path.join(py_src_svn, py_file),
                        to_dir=swig_py_svn)

  print('-- Running Swig Python tests --')
  sys.stdout.flush()

  pythonpath = swig_py_dir
  if 'PYTHONPATH' in os.environ:
    pythonpath += os.pathsep + os.environ['PYTHONPATH']

  python_exe = 'python.exe'
  old_cwd = os.getcwd()
  try:
    os.environ['PYTHONPATH'] = pythonpath

    r = subprocess.call([
              python_exe,
              os.path.join(py_src, 'tests', 'run_all.py')
              ])
  finally:
    os.chdir(old_cwd)

    if (r != 0):
      print('[Test runner reported failure]')
      failed = True

elif test_swig == 'ruby':
  failed = False

  if 'ruby' not in gen_obj._libraries:
    print('Ruby not found. Skipping Ruby tests')
  else:
    ruby_lib = gen_obj._libraries['ruby']

    ruby_exe = 'ruby.exe'
    ruby_subdir = os.path.join('subversion', 'bindings', 'swig', 'ruby')
    ruby_args = [
        '-I', os.path.join(abs_srcdir, ruby_subdir),
        os.path.join(abs_srcdir, ruby_subdir, 'test', 'run-test.rb'),
        '--verbose'
      ]

    print('-- Running Swig Ruby tests --')
    sys.stdout.flush()
    old_cwd = os.getcwd()
    try:
      os.chdir(ruby_subdir)

      os.environ["BUILD_TYPE"] = objdir
      os.environ["SVN_DBG_NO_ABORT_ON_ERROR_LEAK"] = 'YES'
      r = subprocess.call([ruby_exe] + ruby_args)
    finally:
      os.chdir(old_cwd)

    sys.stdout.flush()
    sys.stderr.flush()
    if (r != 0):
      print('[Test runner reported failure]')
      failed = True

# Stop service daemon, if any
if daemon:
  del daemon

# Remove the execs again
for tgt in copied_execs:
  try:
    if os.path.isfile(tgt):
      if verbose:
        print("kill: %s" % tgt)
      os.unlink(tgt)
  except:
    traceback.print_exc(file=sys.stdout)
    pass


if failed:
  sys.exit(1)