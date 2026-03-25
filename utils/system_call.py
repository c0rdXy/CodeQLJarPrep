import os
import shutil
import zipfile
import subprocess
from utils.logger import log


def check(require_ant=False, require_codeql=False):
    if check_cmd(["java", "-h"]) is False:
        log.error("java command not exists")
        exit(1)
    if check_cmd(["ant", "-h"]) is False:
        if require_ant:
            log.error("ant command not exists")
            exit(1)
        log.warning("ant command not exists")
    if require_codeql and check_cmd(["codeql", "version"]) is False:
        log.error("codeql command not exists")
        exit(1)


def check_cmd(command):
    executable = shutil.which(command[0])
    if executable is None:
        return False
    try:
        with open(os.devnull, 'w') as null:
            subprocess.call([executable] + command[1:], stderr=subprocess.STDOUT, stdout=null)
        return True
    except OSError:
        return False


def system_call(command, cwd=None):
    res = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        cwd=cwd
    )
    if res.returncode == 0:
        return True, res.stdout
    return False, res.stderr


def procyon_decompile(decompiler_path, jar_path, out_path):
    cmd = ["java", "-jar", decompiler_path, "-dgs=true", jar_path, "-o", out_path]
    return system_call(cmd)


def java_decompiler(decompiler_path, jar_path, out_path):
    cmd = [
        "java", "-cp", decompiler_path,
        "org.jetbrains.java.decompiler.main.decompiler.ConsoleDecompiler",
        "-dgs=true", jar_path, out_path
    ]
    return system_call(cmd)


def codeql_database_create(database_path, source_root):
    cmd = [
        "codeql", "database", "create", database_path,
        "--language=java",
        "--command=ant -f build.xml",
        "--source-root", "."
    ]
    return system_call(cmd, cwd=source_root)


def unzip(zip_path):
    with zipfile.ZipFile(zip_path) as zip_file:
        for file_name in zip_file.namelist():
            zip_file.extract(file_name, os.path.join(os.path.dirname(zip_path), "src2"))
