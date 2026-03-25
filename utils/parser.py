import argparse


def parse():
    usage = "CodeQLJarPrep [options]"
    parser = argparse.ArgumentParser(prog='CodeQLJarPrep', usage=usage)
    parser.add_argument(
        '-jar',
        dest='jar_path',
        action='store',
        required=True,
        help='指定jar包路径，或包含多个jar包的文件夹路径'
    )
    parser.add_argument(
        '-out',
        dest='out_path',
        action='store',
        required=False,
        help='指定输出目录；批量模式下作为输出根目录'
    )
    parser.add_argument(
        '-tomcat',
        dest='tomcat_path',
        action='store',
        required=False,
        default=False,
        help='按需引入 Tomcat lib/bin 到 classpath；仅传统 Tomcat Web 应用需要，如:/usr/local/apache-tomcat-8.5.75'
    )
    parser.add_argument(
        '-xml',
        dest='build_xml',
        action='store_true',
        required=False,
        help='自动生成build.xml文件, default: false'
    )
    parser.add_argument(
        '-codeql',
        dest='codeql_path',
        nargs='?',
        const=True,
        default=False,
        help='反编译后自动生成CodeQL数据库；不传值时默认输出到反编译目录中的 jar名-database'
    )
    parser.add_argument(
        '-java',
        dest='java_version',
        action='store',
        required=False,
        default='auto',
        help='指定 Java 编译版本，如 8/11/17/21；默认 auto，会从 jar 自动推断'
    )
    args = parser.parse_args()
    return args.__dict__
