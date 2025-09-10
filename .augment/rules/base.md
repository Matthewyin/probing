---
type: "always_apply"
---

-----

### **AI Agent 基础编码准则 (Core Coding Mandate)**

**核心思想：** 代码是写给人读的，顺便让机器执行。一个优秀的AI Agent，其智能不仅体现在算法模型上，更体现在其代码的工程健壮性与生命力上。

-----

### **第一章：灵活性与可扩展性 (Flexibility & Scalability)**

这是构建一切复杂系统的基石。AI Agent的需求是不断变化的，必须从第一行代码开始就为此做准备。

#### **规则 1.1：【绝对禁止】硬编码 (No Hardcoding)**

  * **(The "What") 做什么：**
    严禁在代码中直接写入任何配置型或环境相关的“魔术值”（Magic Values）。这包括但不限于：

      * API密钥、数据库密码、认证Token
      * 文件路径 (`/data/input.csv`)
      * URL端点 (`https://api.example.com/v1/users`)
      * 业务阈值 (例如 `max_retries = 3`, `temperature_setting = 0.7`)

  * **(The "How") 怎么做：**
    将所有可变配置项外部化，通过统一的配置管理机制加载。

    **示例 (Python):**

    **错误的做法 👎**

    ```python
    def call_external_api(data):
        api_key = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # 硬编码密钥
        url = "https://api.service.com/v1/process"   # 硬编码URL
        headers = {"Authorization": f"Bearer {api_key}"}
        # ... a call using requests library
    ```

    **正确的做法 👍**

    1.  **使用 `.env` 文件和环境变量:**
        在项目根目录创建 `.env` 文件 (并将其加入 `.gitignore` 防止泄露):
        ```
        # .env file
        API_SERVICE_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        API_SERVICE_URL="https://api.service.com/v1/process"
        ```
    2.  **在代码中加载:**
        ```python
        import os
        from dotenv import load_dotenv # 需要 'pip install python-dotenv'

        # 在应用启动时加载环境变量
        load_dotenv()

        def call_external_api(data):
            # 从环境中读取配置，提供了灵活性
            api_key = os.getenv("API_SERVICE_KEY")
            url = os.getenv("API_SERVICE_URL")

            if not api_key or not url:
                raise ValueError("API credentials or URL not found in environment variables.")

            headers = {"Authorization": f"Bearer {api_key}"}
            # ... a call using requests library
        ```

  * **(The "Why") 为什么：**

    1.  **安全 (Security):** 将密钥等敏感信息与代码分离，可以避免将其意外提交到版本控制系统（如Git），这是安全领域的头号准则。
    2.  **环境隔离 (Environment Isolation):** 你的Agent需要在开发、测试、生产等不同环境中运行。每套环境的数据库地址、API端点都不同。通过外部配置，你可以为不同环境提供不同的`.env`文件，而无需修改任何一行代码。
    3.  **可维护性 (Maintainability):** 当API URL变更或需要轮换密钥时，非开发人员（如运维工程师）可以直接修改配置文件或环境变量来完成部署，无需重新编译或改动代码，极大地降低了维护成本和风险。
    4.  **操作系统交互 (OS Interaction):** 使用环境变量是利用了操作系统的核心功能。程序启动时，OS会为其创建一个进程环境块，其中存储了这些变量。`os.getenv()` 本质上是一个系统调用，直接向OS查询这些值，这是最高效、最通用的跨语言配置方式。

-----

### **第二章：健壮性与错误处理 (Robustness & Error Handling)**

一个Agent必须像一个可靠的工具，而不是一个易碎的玩具。它必须能预见并优雅地处理失败。

#### **规则 2.1：【必须遵守】绝不信任任何外部输入 (Never Trust External Input)**

  * **(The "What") 做什么：**
    对所有来自外部系统的输入（用户提问、API返回、文件内容、数据库查询结果）进行严格的校验和清理（Validation & Sanitization）。

  * **(The "How") 怎么做：**
    在处理数据前，先检查其类型、格式、范围是否符合预期。

    **示例 (Python):**

    ```python
    def process_user_request(request: dict):
        # 错误的做法: 直接访问，如果'user_id'不存在或不是整数，程序会崩溃或产生bug
        # user_id = int(request['user_id'])

        # 正确的做法: 校验先行
        user_id_raw = request.get('user_id')
        if not user_id_raw or not isinstance(user_id_raw, int) or user_id_raw <= 0:
            # 记录日志，并返回一个清晰的错误信息
            log.error(f"Invalid user_id received: {user_id_raw}")
            raise ValueError("A valid positive integer 'user_id' is required.")

        user_id = user_id_raw
        # ... 后续处理逻辑 ...
    ```

  * **(The "Why") 为什么：**

    1.  **系统稳定性 (System Stability):** 无效输入是导致程序崩溃和非预期行为（Bugs）的主要原因。提前拦截可以保证核心逻辑的稳定运行。
    2.  **安全 (Security):** 这是防止注入类攻击（如SQL注入、命令注入）的第一道防线。恶意用户可能会构造特殊输入来利用你的系统漏洞。
    3.  **CPU与内存 (CPU & Memory):** 处理一个格式错误的巨大输入可能会导致内存分配异常或CPU密集型的无效计算，从而造成资源耗尽。校验可以提前拒绝这类攻击或错误，保护系统资源。

-----

### **第三章：可读性与模块化 (Readability & Modularity)**

代码的生命周期中，维护阶段远长于开发阶段。清晰的结构是降低未来维护成本的关键。

#### **规则 3.1：【强制执行】单一职责原则 (Single Responsibility Principle - SRP)**

  * **(The "What") 做什么：**
    每个函数、每个类、每个模块应该只负责一件事情，并且把它做好。

  * **(The "How") 怎么做：**
    将复杂的任务分解成一系列更小、更专注的函数。

    **示例 (Python):**

    **错误的做法 👎 (一个函数做了太多事)**

    ```python
    def handle_user_data(file_path):
        # 1. 读取文件
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # 2. 校验数据
        if 'name' not in data or 'email' not in data:
            raise ValueError("Missing required fields")
            
        # 3. 转换数据格式
        data['name'] = data['name'].upper()
        
        # 4. 存入数据库
        db.save(data)
    ```

    **正确的做法 👍 (职责分离)**

    ```python
    def read_data_from_file(file_path: str) -> dict:
        """只负责从文件读取并解析JSON数据。"""
        # ... (包含 try-except 文件处理)
        
    def validate_user_data(data: dict) -> bool:
        """只负责校验数据结构。"""
        # ...
        
    def transform_user_data(data: dict) -> dict:
        """只负责业务逻辑转换。"""
        # ...
        
    def save_user_to_db(data: dict):
        """只负责与数据库交互。"""
        # ...
        
    def handle_user_data_flow(file_path: str):
        """作为协调者，清晰地编排整个流程。"""
        raw_data = read_data_from_file(file_path)
        if validate_user_data(raw_data):
            transformed_data = transform_user_data(raw_data)
            save_user_to_db(transformed_data)
    ```

  * **(The "Why") 为什么：**

    1.  **可测试性 (Testability):** 小而专注的函数极易进行单元测试。你可以独立测试`validate_user_data`函数，而无需真实的文件或数据库连接。
    2.  **可复用性 (Reusability):** `read_data_from_file`函数可能在系统的其他地方也会被用到。职责分离使得代码复用成为可能。
    3.  **认知负荷 (Cognitive Load):** 当你调试问题时，模块化的代码能让你快速定位到可能出错的区域。一个只做一件事的函数，其逻辑更容易被大脑一次性加载和理解，从而提升排错效率。这直接关系到开发者的心智带宽，是软件工程的核心成本之一。