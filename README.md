# Fluent JSON Configuration Application

一个基于 PyQt5 和 QFluentWidgets 的 JSON 配置编辑器应用程序，提供了丰富的界面组件和工具来管理复杂的 JSON 配置文件。

## 项目结构

```
application/
├── interfaces/           # 用户界面组件
├── tools/                # 各类工具模块
│   ├── algorithm/        # 算法相关工具
│   ├── api_service/      # API 服务接口工具
│   ├── database/         # 数据库操作工具
│   └── nacos/            # Nacos 配置管理工具
├── utils/                # 实用工具模块
├── widgets/              # 自定义控件
├── base.py              # 基础类定义
├── fluent_json_editor.py # 主应用程序入口
└── json_editor.py       # JSON 编辑器核心逻辑
```


## 核心功能

### JSON 配置编辑
- 可视化 JSON 配置文件编辑器
- 支持多种参数类型（checkbox, slider, dropdown, text等）
- 参数分组和子参数管理
- 实时验证和保存功能

### 数据管理工具
- **数据库工具**: PostgreSQL 数据库连接和操作
- **API 服务**: 与各种后端服务通信
- **算法工具**: 数据处理和分析算法
- **Nacos 集成**: 配置管理和服务发现

### 界面组件
- 拖拽式参数配置界面
- 自定义树形控件项
- 多种输入控件（滑块、下拉框、复选框等）
- 日志显示和监控界面

## 主要模块

### JSON 编辑器 (json_editor.py)
- 核心的 JSON 配置编辑功能
- 树形结构展示和编辑
- 参数类型识别和处理
- 配置导入/导出功能

### 工具模块 (tools/)
- **数据库工具**: 连接和操作 PostgreSQL 数据库
- **API 服务**: 与后端服务进行数据交互
- **算法工具**: 提供数据处理算法实现
- **Nacos 工具**: 配置管理和服务发现功能

### 界面组件 (interfaces/)
- 配置设置对话框
- 各类参数编辑对话框
- 服务状态监控界面
- 日志显示对话框

### 自定义控件 (widgets/)
- 可配置的树形控件项
- 拖拽式列表和树形控件
- 图表绘制控件
- 自定义输入控件

## 技术栈

- **Python 3.x**
- **PyQt5**: 图形界面框架
- **QFluentWidgets**: 美化界面组件库
- **PostgreSQL**: 数据库支持
- **Nacos**: 配置管理和服务发现
- **ruamel.yaml**: YAML 配置文件处理
- **httpx**: HTTP 客户端

## 安装依赖

```bash
pip install -r requirements.txt
```


## 使用说明

1. 运行主程序:
   ```bash
   python main.py
   ```


2. 使用界面加载或创建 JSON 配置文件
3. 通过可视化界面编辑配置参数
4. 保存配置并应用到相应服务

## 开发特性

- 模块化设计，易于扩展
- 支持多线程操作
- 完善的日志记录系统
- 异常处理和错误恢复机制
- 配置文件热重载支持

## 联系方式

如有问题请联系: blackma2009@163.com