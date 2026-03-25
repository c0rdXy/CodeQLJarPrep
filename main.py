import os
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from utils.parser import parse
from utils.system_call import *
from utils.build_xml import build_ant_xml
from utils.logger import banner, section, item, step, success, warning, failure, note, duration, percent, log


def normalize_path(path_value):
    if path_value is True:
        return True
    if not path_value:
        return False
    if os.path.isabs(path_value) is False:
        return os.path.abspath(path_value)
    return path_value


def decode_output(output):
    if isinstance(output, bytes):
        return output.decode('utf-8', errors='replace')
    return str(output)


def preview_output(output, max_lines=12):
    text = decode_output(output).strip()
    if not text:
        return 'No details available.'
    lines = text.splitlines()
    if len(lines) > max_lines:
        return '\n'.join(lines[:max_lines] + ['...'])
    return '\n'.join(lines)


def unique_output_dir(base_dir, folder_name, used_names):
    candidate = folder_name
    index = 1

    while True:
        normalized_name = candidate.lower()
        target_dir = os.path.join(base_dir, candidate)
        if normalized_name not in used_names and os.path.exists(target_dir) is False:
            used_names.add(normalized_name)
            return target_dir
        candidate = f'{folder_name}_{index}'
        index += 1


def resolve_database_root(codeql_path):
    if codeql_path is False:
        return False
    if codeql_path is True:
        return True
    return os.path.abspath(codeql_path)


def resolve_single_database_path(source_path, out_path, codeql_path):
    if codeql_path is False:
        return False
    default_name = f'{source_path.stem}-database'
    if codeql_path is True:
        return os.path.join(out_path, default_name)
    return os.path.abspath(codeql_path)


def resolve_batch_database_path(source_path, out_path, database_root, used_names):
    if database_root is False:
        return False
    default_name = f'{source_path.stem}-database'
    if database_root is True:
        return os.path.join(out_path, default_name)
    return unique_output_dir(database_root, default_name, used_names)


def parse_requested_java_version(version_value):
    if version_value is None:
        return None

    normalized = str(version_value).strip().lower()
    if normalized in ('', 'auto'):
        return None

    aliases = {
        '1.5': 5,
        '1.6': 6,
        '1.7': 7,
        '1.8': 8,
    }
    if normalized in aliases:
        return aliases[normalized]

    if normalized.isdigit():
        version = int(normalized)
        if version >= 5:
            return version

    raise ValueError('`-java` 仅支持 auto 或 Java 版本号，例如 8、11、17、21。')


def class_major_to_java_version(major_version):
    if major_version is None or major_version < 45:
        return None
    return major_version - 44


def normalize_java_version_string(version_text):
    if version_text is None:
        return None

    normalized = str(version_text).strip()
    if normalized == '':
        return None

    try:
        return parse_requested_java_version(normalized)
    except ValueError:
        return None


def infer_java_version_from_manifest(archive):
    manifest_name = 'META-INF/MANIFEST.MF'
    if manifest_name not in archive.namelist():
        return None

    try:
        manifest_text = archive.read(manifest_name).decode('utf-8', errors='replace')
    except KeyError:
        return None

    for line in manifest_text.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        if key.strip().lower() in ('build-jdk-spec', 'build-jdk'):
            inferred_version = normalize_java_version_string(value)
            if inferred_version is not None:
                return inferred_version
    return None


def infer_java_version_from_pom(archive):
    pom_names = [
        name for name in archive.namelist()
        if name.lower().startswith('meta-inf/maven/') and name.lower().endswith('/pom.xml')
    ]
    for pom_name in pom_names:
        try:
            pom_text = archive.read(pom_name).decode('utf-8', errors='replace')
            root = ET.fromstring(pom_text)
        except (KeyError, ET.ParseError):
            continue

        namespace = ''
        if root.tag.startswith('{'):
            namespace = root.tag.split('}', 1)[0] + '}'

        candidate_paths = [
            f'.//{namespace}properties/{namespace}java.version',
            f'.//{namespace}properties/{namespace}maven.compiler.source',
            f'.//{namespace}properties/{namespace}maven.compiler.target',
            f'.//{namespace}build/{namespace}plugins/{namespace}plugin/{namespace}configuration/{namespace}source',
            f'.//{namespace}build/{namespace}plugins/{namespace}plugin/{namespace}configuration/{namespace}target',
        ]
        for candidate_path in candidate_paths:
            node = root.find(candidate_path)
            if node is None or node.text is None:
                continue
            inferred_version = normalize_java_version_string(node.text)
            if inferred_version is not None:
                return inferred_version
    return None


def infer_java_version_from_jar(jar_path):
    try:
        with zipfile.ZipFile(jar_path) as archive:
            class_entries = []
            versioned_entries = []
            for entry in archive.infolist():
                if entry.is_dir() or entry.filename.lower().endswith('.class') is False:
                    continue
                if entry.filename.lower().startswith('meta-inf/versions/'):
                    versioned_entries.append(entry.filename)
                else:
                    class_entries.append(entry.filename)

            candidates = class_entries or versioned_entries
            highest_major = None
            for entry_name in candidates:
                with archive.open(entry_name) as class_file:
                    header = class_file.read(8)
                if len(header) < 8 or header[:4] != b'\xca\xfe\xba\xbe':
                    continue
                major_version = int.from_bytes(header[6:8], byteorder='big')
                if highest_major is None or major_version > highest_major:
                    highest_major = major_version
            detected_version = class_major_to_java_version(highest_major)
            if detected_version is not None:
                return detected_version

            manifest_version = infer_java_version_from_manifest(archive)
            if manifest_version is not None:
                return manifest_version

            return infer_java_version_from_pom(archive)
    except (OSError, zipfile.BadZipFile):
        return None


def format_javac_version(java_version):
    if java_version <= 8:
        return f'1.{java_version}'
    return str(java_version)


def resolve_java_config(java_version_option, jar_path):
    requested_version = parse_requested_java_version(java_version_option)
    if requested_version is not None:
        formatted_version = format_javac_version(requested_version)
        return {
            'version': requested_version,
            'source': formatted_version,
            'target': formatted_version,
            'display': f'manual {requested_version}',
            'fallback': False,
        }

    detected_version = infer_java_version_from_jar(jar_path)
    if detected_version is None:
        detected_version = 8
        formatted_version = format_javac_version(detected_version)
        return {
            'version': detected_version,
            'source': formatted_version,
            'target': formatted_version,
            'display': f'auto fallback {detected_version}',
            'fallback': True,
        }

    formatted_version = format_javac_version(detected_version)
    return {
        'version': detected_version,
        'source': formatted_version,
        'target': formatted_version,
        'display': f'auto detected {detected_version}',
        'fallback': False,
    }


def collect_jobs(jar_path, out_path, codeql_path):
    source_path = Path(jar_path)
    if source_path.is_file():
        if source_path.suffix.lower() != '.jar':
            raise ValueError('`-jar` 必须是 jar 文件，或包含 jar 文件的目录。')

        decompile_out = os.path.abspath(out_path) if out_path else os.path.join(str(source_path.parent), source_path.stem)
        database_out = resolve_single_database_path(source_path, decompile_out, codeql_path)
        return [{
            'jar_path': str(source_path.resolve()),
            'out_path': os.path.abspath(decompile_out),
            'database_path': database_out,
        }]

    if source_path.is_dir() is False:
        raise ValueError('输入的 `-jar` 路径不存在。')

    jar_files = sorted(
        [item_path for item_path in source_path.iterdir() if item_path.is_file() and item_path.suffix.lower() == '.jar'],
        key=lambda item_path: item_path.name.lower()
    )
    if not jar_files:
        raise ValueError('指定目录中没有找到 jar 文件。')

    output_root = os.path.abspath(out_path) if out_path else str(source_path.resolve())
    os.makedirs(output_root, exist_ok=True)

    database_root = resolve_database_root(codeql_path)
    if isinstance(database_root, str):
        os.makedirs(database_root, exist_ok=True)

    used_out_names = set()
    used_database_names = set()
    jobs = []
    for jar_file in jar_files:
        stem = jar_file.stem
        current_out_path = unique_output_dir(output_root, stem, used_out_names)
        current_database_path = resolve_batch_database_path(
            jar_file,
            current_out_path,
            database_root,
            used_database_names
        )
        jobs.append({
            'jar_path': str(jar_file.resolve()),
            'out_path': current_out_path,
            'database_path': current_database_path,
        })
    return jobs


def run_step(step_name, runner):
    step(f'{step_name} started')
    started_at = time.perf_counter()
    status, output = runner()
    elapsed = duration(time.perf_counter() - started_at)
    if status:
        success(f'{step_name} completed in {elapsed}')
        return True, output

    failure(f'{step_name} failed after {elapsed}')
    details = preview_output(output)
    for line in details.splitlines():
        log.error('    %s', line)
    return False, output


def process_jar(job, java_decompiler_path, procyon_decompile_path, xml_path, tomcat_path, build_xml, enable_codeql, java_version_option, index, total):
    jar_path = job['jar_path']
    out_path = job['out_path']
    database_path = job['database_path']
    progress = percent(index, total)
    java_config = resolve_java_config(java_version_option, jar_path)

    section(f'Job {index}/{total} ({progress}): {Path(jar_path).name}')
    item('Jar', jar_path)
    item('Output', out_path)
    item('Java', java_config['display'])
    item('Build XML', 'enabled' if build_xml else 'disabled')
    item('CodeQL', database_path if enable_codeql else 'disabled')

    if java_config['fallback']:
        warning('failed to detect Java version from jar, fallback to Java 8 for build.xml')

    started_at = time.perf_counter()
    os.makedirs(out_path, exist_ok=True)
    zip_path = os.path.abspath(os.path.join(out_path, os.path.basename(jar_path)))

    ok, _ = run_step(
        'Procyon decompile',
        lambda: procyon_decompile(procyon_decompile_path, jar_path, os.path.join(out_path, 'src1'))
    )
    if not ok:
        return False

    ok, _ = run_step(
        'JetBrains decompile',
        lambda: java_decompiler(java_decompiler_path, jar_path, out_path)
    )
    if not ok:
        return False

    step('Archive extract started')
    unzip_started = time.perf_counter()
    unzip(zip_path)
    success(f'Archive extracted in {duration(time.perf_counter() - unzip_started)}')

    if build_xml:
        step('build.xml generation started')
        xml_started = time.perf_counter()
        build_ant_xml(xml_path, out_path, tomcat_path, java_config)
        success(f'build.xml generated in {duration(time.perf_counter() - xml_started)}')

    if enable_codeql:
        ok, _ = run_step(
            'CodeQL database create',
            lambda: codeql_database_create(database_path, out_path)
        )
        if not ok:
            return False

    success(f'Job finished in {duration(time.perf_counter() - started_at)}')
    return True


if __name__ == '__main__':
    cmd_parse = parse()
    codeql_path = normalize_path(cmd_parse['codeql_path'])
    build_xml = cmd_parse['build_xml'] or bool(codeql_path)
    check(require_ant=build_xml, require_codeql=bool(codeql_path))

    jar_path = normalize_path(cmd_parse['jar_path'])
    out_path = normalize_path(cmd_parse['out_path'])
    tomcat_path = normalize_path(cmd_parse['tomcat_path'])
    java_version_option = cmd_parse['java_version']

    java_decompiler_path = os.path.abspath(os.path.join('jar', 'java-decompiler.jar'))
    procyon_decompile_path = os.path.abspath(os.path.join('jar', 'procyon-decompiler-0.6.0.jar'))
    xml_path = os.path.abspath('build.xml')

    try:
        requested_java_version = parse_requested_java_version(java_version_option)
        jobs = collect_jobs(jar_path, out_path, codeql_path)
    except ValueError as exc:
        failure(str(exc))
        exit(1)

    if tomcat_path and os.path.exists(tomcat_path) is False:
        warning(f'tomcat path not exists, skip tomcat classpath: {tomcat_path}')
        tomcat_path = False

    total_started = time.perf_counter()
    banner('CodeQLJarPrep')
    section('Execution Plan')
    item('Input', jar_path)
    item('Jobs', len(jobs))
    item('Output Root', out_path if out_path else 'auto')
    item('Java', f'manual {requested_java_version}' if requested_java_version is not None else 'auto per jar')
    item('Build XML', 'enabled' if build_xml else 'disabled')
    item('CodeQL', codeql_path if codeql_path else 'disabled')
    item('Tomcat', tomcat_path if tomcat_path else 'disabled')
    note('Batch progress will be shown as Job current/total (percentage).')

    success_count = 0
    for index, job in enumerate(jobs, start=1):
        if process_jar(
            job,
            java_decompiler_path,
            procyon_decompile_path,
            xml_path,
            tomcat_path,
            build_xml,
            bool(codeql_path),
            java_version_option,
            index,
            len(jobs)
        ):
            success_count += 1

    failed_count = len(jobs) - success_count
    success_rate = percent(success_count, len(jobs))
    section('Summary')
    item('Successful', success_count)
    item('Failed', failed_count)
    item('Success Rate', success_rate)
    item('Elapsed', duration(time.perf_counter() - total_started))

    if failed_count:
        failure('Execution finished with failures.')
        exit(1)

    success('Execution finished successfully.')
