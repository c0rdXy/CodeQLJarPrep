## 项目简介

`CodeQLJarPrep` 用于将 `jar` 包整理为可供 Apache Ant / CodeQL 使用的工程目录。

它会串联以下流程：

- 反编译 jar
- 解压原始归档内容
- 生成适合 `ant` 编译的 `build.xml`
- 可选直接创建 CodeQL 数据库

这个工具适合在没有源码、只有编译产物时，为后续的 Java 静态分析做预处理。

## 功能

- 支持单个 jar 反编译
- 支持批量处理目录中的多个 jar
- 自动生成 `build.xml`
- 可选引入外部 Tomcat 依赖目录
- 可选自动创建 CodeQL 数据库
- 支持多版本 Java
- 默认自动从 jar 中的 `.class` 字节码推断 Java 版本
- 当 jar 中无法直接读取 `.class` 版本时，会回退读取 `MANIFEST.MF` / `pom.xml`
- 支持通过命令行手动指定 Java 编译版本
- 自动识别实际存在源码的目录并写入 `src.dir`

## 目录结构

```text
CodeQLJarPrep/
├─ main.py
├─ build.xml
├─ jar/
│  ├─ java-decompiler.jar
│  └─ procyon-decompiler-0.6.0.jar
└─ utils/
   ├─ parser.py
   ├─ system_call.py
   ├─ build_xml.py
   └─ logger.py
```

## 依赖

- Python 3
- Java 8+
- Apache Ant
- CodeQL CLI

说明：

- 使用 `-xml` 时需要本机可执行 `ant`
- 使用 `-codeql` 时需要本机可执行 `codeql`
- 生成的 `build.xml` 会按目标 Java 版本写入 `source` / `target`
- 运行 `ant` / `codeql` 时，建议本机 JDK 版本不低于目标版本

## 参数说明

```shell
python main.py -h
```

当前支持的主要参数：

- `-jar`：指定单个 jar 文件，或包含多个 jar 的目录
- `-out`：指定输出目录；批量模式下作为输出根目录
- `-tomcat`：指定 Tomcat 目录，将其 `lib` / `bin` 加入 classpath，仅在目标 jar 依赖外部 Tomcat / Servlet 容器类时使用
- `-xml`：自动生成 `build.xml`
- `-codeql [PATH]`：反编译完成后自动创建 CodeQL 数据库
- `-java VERSION`：指定 Java 编译版本，如 `8`、`11`、`17`、`21`

`-tomcat` 的行为：

- 默认不需要传
- 适用于传统 Tomcat 部署的 Web 应用，且反编译代码依赖 `javax.servlet.*`、`jakarta.servlet.*`、`org.apache.catalina.*` 等容器类
- 传入后，会把指定 Tomcat 目录下的 `lib` / `bin` 加入生成的 `build.xml` classpath
- 对普通 jar 或自带依赖的 Spring Boot fat jar，通常不需要传
- 如果目标 jar 编译时缺少容器相关类，再考虑补充该参数

`-java` 的行为：

- 默认值为 `auto`
- `auto` 模式下，会优先从 jar 内普通 `.class` 文件推断版本
- 如果是多版本 jar 且存在 `META-INF/versions/`，会优先使用基础 class，而不是直接取版本覆盖层
- 如果 jar 中拿不到 `.class` 版本信息，会继续尝试读取 `META-INF/MANIFEST.MF` 中的构建 JDK 信息，以及 `META-INF/maven/**/pom.xml` 中的 Java 版本配置
- 如果无法推断，会回退为 Java 8
- 手动指定后，会统一将 `build.xml` 中的 `source` / `target` 设置为对应版本

## 使用示例

### 查看帮助

```shell
python main.py -h
```

### 反编译单个 jar

显式指定输出目录：

```shell
python main.py -jar java-sec.jar -out java-sec-decompile -xml
```

如果不指定 `-out`，默认在 jar 同级目录生成同名输出文件夹：

```shell
python main.py -jar java-sec.jar -xml
```

### 指定 Java 版本

手动按 Java 8 生成 `build.xml`：

```shell
python main.py -jar java-sec.jar -xml -java 8
```

手动按 Java 17 生成 `build.xml`：

```shell
python main.py -jar java-sec.jar -xml -java 17
```

使用默认自动检测：

```shell
python main.py -jar java-sec.jar -xml -java auto
```

### 批量处理 jar

传入一个目录时，会扫描该目录第一层下的 `.jar` 文件，并为每个 jar 生成一个同名输出目录。

如果同名目录已存在，会自动追加数字后缀，例如 `demo_1`。

默认输出到输入目录下：

```shell
python main.py -jar ./jars -xml
```

指定统一输出根目录：

```shell
python main.py -jar ./jars -out ./output -xml
```

批量模式下手动统一指定 Java 11：

```shell
python main.py -jar ./jars -out ./output -xml -java 11
```

批量模式下使用自动检测时，每个 jar 会分别推断自己的 Java 版本。

### 按需引入 Tomcat 依赖

仅当目标 jar 不是自包含应用，而是依赖外部 Tomcat 提供的运行库时再使用，例如传统 servlet / JSP Web 应用：

```shell
python main.py -jar java-sec.jar -out java-sec-decompile -tomcat /usr/local/apache-tomcat-8.5.75 -xml
```

如果是普通 jar，或是已经在 `BOOT-INF/lib` 中自带依赖的 Spring Boot 可执行 jar，通常不需要 `-tomcat`。

### 自动创建 CodeQL 数据库

不带值使用 `-codeql` 时，会在每个反编译输出目录内创建一个默认数据库目录：

```shell
python main.py -jar java-sec.jar -codeql
```

默认数据库目录名称为 `jar包名-database`，例如：

```text
java-sec-decompile/
  build.xml
  src1/
  src2/
  java-sec-database/
```

也可以显式指定数据库输出路径：

```shell
python main.py -jar java-sec.jar -out java-sec-decompile -codeql ./databases/java-sec-db
```

批量模式下，如果给 `-codeql` 传的是目录，则会在该目录下按每个 jar 生成独立数据库目录：

```shell
python main.py -jar ./jars -out ./output -codeql ./databases
```

启用 `-codeql` 时，即使不传 `-xml` 也会自动生成 `build.xml`，因为建库命令会使用：

```shell
ant -f build.xml
```

### 组合示例

自动检测 Java 版本并建库：

```shell
python main.py -jar java-sec.jar -out java-sec-decompile -codeql
```

手动指定 Java 17，为传统 Tomcat Web 应用补充容器依赖并建库：

```shell
python main.py -jar java-sec.jar -out java-sec-decompile -tomcat /usr/local/apache-tomcat-8.5.75 -java 17 -codeql
```

## 输出目录说明

典型输出目录结构如下：

```text
java-sec-decompile/
├─ build.xml
├─ src1/
├─ src2/
└─ java-sec-database/
```

含义如下：

- `src1/`：反编译后的 Java 源码
- `src2/`：从 jar 中解压出的原始内容
- `build.xml`：供 Ant / CodeQL 使用的构建文件
- `*-database/`：CodeQL 数据库目录

## build.xml 版本策略

生成 `build.xml` 时会自动处理 Java 版本：

- Java 8 及以下会写成 `1.8`、`1.7` 这类格式
- Java 9 及以上会写成 `9`、`11`、`17`、`21` 这类格式
- 版本来自 `-java` 手动指定，或 jar 自动检测结果
- `src.dir` 会自动指向第一个实际包含 `.java` 文件的目录，优先级为 `src1`、`src2/BOOT-INF/classes`、`src2`
- `javac` 默认使用 `fork="true"`、`includeantruntime="false"`、`encoding="UTF-8"`，以提升不同环境下的兼容性

例如：

- `-java 8` 会生成 `source="1.8" target="1.8"`
- `-java 17` 会生成 `source="17" target="17"`

## 手动 CodeQL 建库示例

进入生成后的输出目录后执行：

```shell
codeql database create tmp-database --language=java --command="ant -f build.xml" --source-root ./
```

## 注意事项

- 批量模式只扫描输入目录第一层的 `.jar` 文件，不递归子目录
- 自动检测 Java 版本优先依赖 jar 中的 `.class` 文件；无法直接读取时会尝试从 manifest / pom 推断，仍失败时才回退到 Java 8
- 如果目标 jar 依赖额外容器或第三方库，可能仍需补充 classpath
- 反编译结果受反编译器本身能力限制，不能保证 100% 还原源码
