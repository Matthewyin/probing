---
type: "always_apply"
---

AI Agent 多语言编码准则准则核心哲学一份代码的生命周期中，90%的时间用于维护。我们编写的规则，旨在优化这90%的成本。每一条规则不仅告诉你 “做什么”(The What)，更解释 “怎么做”(The How) 和 “为什么这么做”(The "Why")，深入到语言、系统甚至硬件的交互层面。1. Python 编码准则Python以其简洁和强大的生态系统成为AI领域的首选语言。规则的重点在于保持这种简洁性，同时通过类型提示和现代库来构建企业级的健壮性。规则 1.1: 【绝对禁止】硬编码 - 使用Pydantic进行配置管理(The "What") 做什么:将所有配置（API密钥、模型名称、URL、业务参数）集中管理，并通过类型校验加载。(The "How") 怎么做:使用 Pydantic 定义一个配置模型，它可以自动从环境变量中读取、转换和校验配置。示例:# 1. 安装 pydantic 和 python-dotenv
# pip install pydantic python-dotenv pydantic-settings

# 2. 在 .env 文件中定义配置 (此文件应在 .gitignore 中)
# APP_NAME="Intelligent Search Agent"
# OPENAI_API_KEY="sk-xxxxxxxxxx"
# MAX_SEARCH_RESULTS=5
# TEMPERATURE=0.5

# 3. 在 config.py 中定义配置模型
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    # model_config用于指定从.env文件加载
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    APP_NAME: str = "Default Agent Name"
    OPENAI_API_KEY: str
    MAX_SEARCH_RESULTS: int
    TEMPERATURE: float

    # 你可以在这里添加校验逻辑
    # @validator('TEMPERATURE')
    # def temperature_must_be_in_range(cls, v):
    #     if not 0.0 <= v <= 1.0:
    #         raise ValueError('Temperature must be between 0.0 and 1.0')
    #     return v

# 4. 在应用中使用
# from config import AppSettings
# settings = AppSettings()
# print(f"Agent Name: {settings.APP_NAME}")
# print(f"OpenAI Key loaded: {settings.OPENAI_API_KEY is not None}")
(The "Why") 为什么:Pydantic 不仅仅是读取配置。它在程序启动时就强制进行了 类型校验。如果一个本应是整数的配置（如MAX_SEARCH_RESULTS）被错误地写成了字符串，程序会立刻失败并给出明确的错误信息，而不是在运行时深入到业务逻辑后才触发一个隐晦的TypeError。这是一种 “Fail Fast” 哲学，能极大地缩短调试周期。规则 1.2: 【必须遵守】健壮性 - 用Pydantic校验外部输入(The "What") 做什么:所有进入Agent的外部数据（API响应、用户输入）都必须通过一个Pydantic模型进行解析和校验。(The "How") 怎么做:为每个预期的外部数据结构定义一个Pydantic模型。示例:import pydantic

class UserQuery(pydantic.BaseModel):
    user_id: int
    query_text: str
    options: dict | None = None # 可选字段

def process_request(request_data: dict):
    try:
        query = UserQuery.model_validate(request_data)
        # 从这里开始，你可以绝对信任 query 对象的结构和类型
        print(f"Processing query for user: {query.user_id}")
        # ... 业务逻辑
    except pydantic.ValidationError as e:
        # 优雅地处理校验失败
        print(f"Invalid request data: {e}")
        # 返回一个清晰的错误给调用方
        raise ValueError("Invalid input provided.")
(The "Why") 为什么:在动态类型的Python中，最大的风险源于数据在系统流转过程中形态和类型的未知性。Pydantic模型为这些数据在进入你系统的入口处设立了一个“类型屏障”。一旦数据通过了这个屏障，它就被转换成了一个结构清晰、类型确定的Python对象。这消除了在代码各处进行isinstance()和'key' in dict检查的需要，让核心业务逻辑变得异常干净和可靠。这本质上是在运行时享受到了静态类型语言的部分好处。规则 1.3: 【强制执行】模块化 - 使用清晰的模块和类型提示(The "What") 做什么:遵循单一职责原则，将Agent的功能分解到不同的模块（.py文件）中，并对所有函数签名使用 类型提示 (Type Hinting)。(The "How") 怎么做:项目结构示例：/my_agent
    ├── main.py             # 应用入口和流程编排
    ├── config.py           # 配置管理 (如上)
    ├── models.py           # Pydantic 数据模型 (如上)
    ├── services/
    │   ├── __init__.py
    │   ├── llm_service.py    # 封装与大语言模型的交互
    │   └── search_service.py # 封装外部搜索API的交互
    └── utils/
        ├── __init__.py
        └── text_parser.py    # 文本处理工具函数
示例 llm_service.py:from models import UserQuery # 从模型模块导入
from config import AppSettings

def generate_response(query: UserQuery, settings: AppSettings) -> str:
    """
    Generates a response using the LLM based on the user query.

    Args:
        query: A validated UserQuery object.
        settings: The application settings.

    Returns:
        The generated text response.
    """
    # ... 与OpenAI或其他LLM交互的逻辑
    # 使用 settings.OPENAI_API_KEY 和 settings.TEMPERATURE
    prompt = f"User '{query.user_id}' asked: {query.query_text}"
    # response = openai.Completion.create(...)
    # return response.choices[0].text
    return "This is a mocked response."
(The "Why") 为什么:类型提示 是现代Python的基石。虽然CPython解释器在运行时会忽略它们，但它们为开发者和工具（如MyPy, VS Code的Pylance）提供了关键的元信息。这使得 静态代码分析 成为可能，可以在代码运行前就发现大量潜在的类型错误。这极大地提升了大型项目的可维护性，并提供了可靠的自动补全，其效果堪比静态语言，同时保留了Python的开发速度。2. JavaScript / TypeScript 编码准则在Node.js环境中，规则的核心是拥抱异步特性，并利用TypeScript的类型系统在动态的JS世界中建立秩序。规则 2.1: 【绝对禁止】硬编码 - 标准化环境变量(The "What") 做什么:所有配置项必须通过环境变量加载。(The "How") 怎么做:使用 dotenv 库在开发环境中加载 .env 文件，在生产环境中直接读取由部署平台注入的环境变量。示例:// 1. 安装
// npm install dotenv

// 2. 在 .env 文件中定义
// API_KEY="your-secret-key"
// API_URL="[https://api.example.com](https://api.example.com)"

// 3. 在应用入口 (e.g., index.ts) 加载
import dotenv from 'dotenv';
dotenv.config(); // 读取 .env 文件并加载到 process.env

// 4. 创建一个集中的配置导出文件 config.ts
export const config = {
    apiKey: process.env.API_KEY,
    apiUrl: process.env.API_URL,
};

// 5. 在其他地方使用
// import { config } from './config';
// if (!config.apiKey) {
//   throw new Error("API_KEY is not defined in environment variables");
// }
(The "Why") 为什么:process.env 是Node.js与底层操作系统交互的标准接口。这种方式与容器化（Docker）和云原生部署（Kubernetes, Serverless）的工作流完全兼容。配置与代码包分离，使得同一个Docker镜像可以不做任何修改就部署到开发、测试、生产等任何环境中，这符合“一次构建，随处运行”的原则。规则 2.2: 【必须遵守】健壮性 - 使用Zod进行输入校验(The "What") 做什么:对所有外部输入（特别是API的请求体和响应）使用 zod 进行严格的模式校验和类型推断。(The "How") 怎么做:zod 允许你定义一个 schema，然后用它来解析未知输入。如果解析成功，你将得到一个完全类型化的对象。示例:// 1. 安装: npm install zod
import { z } from 'zod';

// 2. 定义 Schema
const UserQuerySchema = z.object({
  userId: z.number().int().positive(),
  queryText: z.string().min(1),
  options: z.record(z.any()).optional(),
});

// 3. 从 Schema 推断 TypeScript 类型
type UserQuery = z.infer<typeof UserQuerySchema>;

// 4. 在处理函数中使用
function processRequest(requestData: unknown): void {
  try {
    // Zod 会解析、校验并返回一个类型安全的对象
    const query: UserQuery = UserQuerySchema.parse(requestData);

    // 从这里开始，'query' 变量被 TypeScript 静态地认为是 UserQuery 类型
    console.log(`Processing query for user: ${query.userId}`);
    // ... 业务逻辑

  } catch (error) {
    if (error instanceof z.ZodError) {
      console.error("Validation failed:", error.errors);
      // 返回 400 Bad Request
    }
    throw error;
  }
}
(The "Why") 为什么:TypeScript在 编译时 提供类型安全，但它无法保证 运行时 从外部（如JSON API）接收到的数据符合你的interface定义。zod 填补了这个空白。它在运行时扮演“类型守卫”的角色。更强大的是，它的z.infer功能可以从你的运行时校验逻辑（Schema） 自动生成 编译时类型（TypeScript Type）。这保证了运行时和编译时的一致性，消除了手动维护两套类型定义的冗余和风险，是目前TypeScript生态中的最佳实践。规则 2.3: 【强制执行】异步流程控制 - 全程使用async/await(The "What") 做什么:所有异步操作（文件I/O, 网络请求, 数据库调用）必须使用 async/await 语法，并配合 try/catch 进行错误处理。严禁使用回调地狱（Callback Hell）或裸.then()链。(The "How") 怎么做:将异步逻辑封装在 async 函数中，并用 try/catch 包裹 await 调用。示例:import { z } from 'zod'; // 假设 Zod Schema 已定义

// 定义API响应的Schema
const ApiDataSchema = z.object({ /* ... */ });
type ApiData = z.infer<typeof ApiDataSchema>;

async function fetchDataFromApi(url: string): Promise<ApiData> {
    try {
        const response = await fetch(url);

        if (!response.ok) {
            // 处理 HTTP 错误
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data: unknown = await response.json();

        // 使用 Zod 校验响应体
        const validatedData = ApiDataSchema.parse(data);

        return validatedData;

    } catch (error) {
        console.error("Failed to fetch or validate API data:", error);
        // 向上抛出或处理错误
        throw new Error("Could not retrieve data from the external service.");
    }
}
(The "Why") 为什么:async/await 是构建在 Promise 之上的语法糖，但它从根本上改变了异步代码的可读性。它让异步代码看起来像同步代码，使得逻辑流程非常清晰。在底层，V8引擎的 事件循环（Event Loop） 仍然在高效地处理非阻塞I/O。当await一个Promise时，V8会将当前函数的执行上下文暂停，并将其从调用栈中弹出，去执行其他任务。当Promise完成时，事件循环会将一个恢复该函数执行的任务（一个微任务）放入队列。这种机制使得Node.js可以用单线程处理海量的并发I/O请求，而async/await是我们与这个强大机制交互的最优雅、最不易出错的方式。3. Java 编码准则Java的优势在于其强类型系统、成熟的生态（Spring）和高性能的JVM。规则旨在充分利用这些优势，构建大型、稳定、可维护的Agent系统。规则 3.1: 【绝对禁止】硬编码 - 使用Spring Boot配置管理(The "What") 做什么:所有配置项通过 application.yml 或 application.properties 文件管理，并使用类型安全的方式注入到代码中。(The "How") 怎么做:使用 @ConfigurationProperties 创建一个类型安全的配置类。示例:在 src/main/resources/application.yml 中定义:agent:
  name: "Financial Analyst Agent"
  llm:
    provider: "openai"
    api-key: "${OPENAI_API_KEY}" # 可以从环境变量引用
    temperature: 0.6
  search:
    max-results: 10
创建配置属性类 AgentProperties.java:package com.example.agent.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
// ...其他校验注解

@ConfigurationProperties(prefix = "agent")
// @Validated // 启用 JSR-303 校验
public record AgentProperties(
    @NotBlank String name,
    Llm llm,
    Search search
) {
    public record Llm(@NotBlank String provider, @NotBlank String apiKey, double temperature) {}
    public record Search(@Positive int maxResults) {}
}
在主应用或配置类中启用:@SpringBootApplication
@EnableConfigurationProperties(AgentProperties.class)
public class AgentApplication {
    // ...
}
在Service中注入并使用:@Service
public class ChatService {
    private final AgentProperties agentProperties;

    // 通过构造函数注入
    public ChatService(AgentProperties agentProperties) {
        this.agentProperties = agentProperties;
    }

    public void doSomething() {
        System.out.println("Using LLM provider: " + agentProperties.llm().provider());
        System.out.println("API Key loaded: " + !agentProperties.llm().apiKey().isEmpty());
    }
}
(The "Why") 为什么:Spring Boot的 @ConfigurationProperties 提供了 编译时安全 的配置访问。如果你在代码中写错了属性名（例如 agentProperties.llm().provder()），编译器会立刻报错。它还集成了JSR-303/JSR-380 Bean Validation，可以在应用启动时自动校验配置（如apiKey不能为空，maxResults必须是正数），实现了与Python Pydantic类似的“Fail Fast”哲学。这一切都构建在Java强大的类型系统和Spring的依赖注入容器之上，是企业级Java应用的最佳实践。规则 3.2: 【必须遵守】健壮性 - 使用Optional和自定义异常(The "What") 做什么:绝不返回 null。对于可能不存在的结果，使用 java.util.Optional。对于可预期的错误，定义并抛出具体的、受检（Checked）或非受检（Unchecked）的业务异常。(The "How") 怎么做:示例:// 自定义业务异常
public class DocumentNotFoundException extends RuntimeException {
    public DocumentNotFoundException(String docId) {
        super("Document with ID '" + docId + "' could not be found.");
    }
}

@Repository
public class DocumentRepository {
    // 模拟数据库
    private final Map<String, String> storage = new HashMap<>();

    public Optional<String> findById(String docId) {
        // 使用 Optional 包装可能为 null 的结果
        return Optional.ofNullable(storage.get(docId));
    }
}

@Service
public class DocumentService {
    private final DocumentRepository repository;

    public DocumentService(DocumentRepository repository) { this.repository = repository; }

    public String getDocumentContent(String docId) {
        // 使用 orElseThrow 来优雅地处理空结果
        return repository.findById(docId)
            .orElseThrow(() -> new DocumentNotFoundException(docId));
    }
}
(The "Why") 为什么:NullPointerException (NPE) 被称为“十亿美元的错误”。Optional 是一个容器对象，它通过类型系统强制调用者去显式地处理“值不存在”的情况，从而在 编译层面 极大地减少了NPE的可能性。自定义异常则让错误处理更具语境。当上层代码捕获一个DocumentNotFoundException时，它清楚地知道发生了什么，而不是面对一个模糊的RuntimeException。这使得构建弹性和可恢复的系统（例如，通过全局异常处理器向用户返回一个清晰的404 Not Found响应）成为可能。规则 3.3: 【强制执行】模块化 - 面向接口编程和依赖注入(The "What") 做什么:组件之间通过接口（interface）进行通信，而不是具体的实现类。使用Spring的依赖注入（DI）来管理组件的生命周期和依赖关系。(The "How") 怎么做:示例:// 1. 定义接口
public interface LanguageModelService {
    String generateResponse(String prompt);
}

// 2. 创建一个实现 (可以有多个，如OpenAI, Gemini)
@Service("openAI")
public class OpenAiService implements LanguageModelService {
    private final AgentProperties properties;
    // ... 注入 RestClient 或其他依赖

    public OpenAiService(AgentProperties properties) { this.properties = properties; }

    @Override
    public String generateResponse(String prompt) {
        // 使用 properties.llm().apiKey() 调用 OpenAI API
        return "Response from OpenAI";
    }
}

// 3. 在另一个服务中注入接口
@Service
public class AgentWorkflowService {
    private final LanguageModelService llmService;

    // 通过构造函数注入。Spring会根据上下文找到一个实现类 (或使用@Qualifier指定)
    public AgentWorkflowService(LanguageModelService llmService) {
        this.llmService = llmService;
    }

    public String runWorkflow(String userInput) {
        // ...
        String response = llmService.generateResponse(userInput);
        // ...
        return response;
    }
}
(The "Why") 为什么:面向接口编程是实现 “高内聚，低耦合” 的核心手段。AgentWorkflowService 不关心它使用的是OpenAiService还是GeminiService，它只关心对方遵守了LanguageModelService的契约。这使得系统极易扩展和测试。你可以轻松地换掉LLM的实现而无需修改任何业务逻辑代码。在测试中，你可以注入一个MockLanguageModelService来模拟LLM的行为，从而实现快速、可靠的单元测试。依赖注入（DI） 和 控制反转（IoC） 是Spring框架的基石，它将对象的创建和依赖关系的管理权从代码中移交给了框架。这种模式解耦了组件，是构建大型、可维护系统的关键。4. Go 编码准则Go的设计哲学是“少即是多”。它的规则强调简洁、明确和高效的并发。规则 4.1: 【绝对禁止】硬编码 - 使用Viper进行全面配置(The "What") 做什么:使用 Viper 库统一管理来自文件、环境变量、远程K/V存储的配置。(The "How") 怎么做:Viper 可以无缝地整合多种配置源，并将其解析到Go的struct中。示例:// 1. 安装: go get [github.com/spf13/viper](https://github.com/spf13/viper)
package main

import (
	"fmt"
	"[github.com/spf13/viper](https://github.com/spf13/viper)"
)

// 定义与配置结构匹配的 struct
type Config struct {
	AppName string `mapstructure:"APP_NAME"`
	ApiKey  string `mapstructure:"API_KEY"`
	Search  struct {
		MaxResults int `mapstructure:"MAX_RESULTS"`
	} `mapstructure:"SEARCH"`
}

func LoadConfig() (Config, error) {
    // 设置默认值
	viper.SetDefault("APP_NAME", "Default Go Agent")

    // 绑定环境变量
	viper.BindEnv("APP_NAME")
	viper.BindEnv("API_KEY")
	viper.BindEnv("SEARCH.MAX_RESULTS")

    // 也可以从文件读取 (可选)
	// viper.SetConfigName("config")
	// viper.AddConfigPath(".")
	// if err := viper.ReadInConfig(); err != nil { ... }

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return Config{}, fmt.Errorf("unable to decode into struct: %w", err)
	}
	return config, nil
}

func main() {
    // 在启动时加载
    // 记得设置环境变量:
    // export APP_NAME="My Go Agent"
    // export API_KEY="secret-key"
    // export SEARCH_MAX_RESULTS=15
	cfg, err := LoadConfig()
	if err != nil {
		panic(err)
	}
	fmt.Printf("App Name: %s\n", cfg.AppName)
	fmt.Printf("API Key loaded: %t\n", cfg.ApiKey != "")
	fmt.Printf("Max Results: %d\n", cfg.Search.MaxResults)
}
(The "Why") 为什么:Viper 的强大之处在于其 配置优先级 系统。它允许你定义一个查找配置的顺序，例如：首先检查命令行标志，然后是环境变量，然后是配置文件，最后是默认值。这为应用程序部署提供了极大的灵活性。struct tag (mapstructure) 的使用则提供了类型安全的配置访问，将非结构化的配置源映射到Go的强类型系统中。规则 4.2: 【必须遵守】健壮性 - 显式处理每一个error(The "What") 做什么:任何可能返回错误的函数，都必须在其返回签名中包含一个error类型。调用这样的函数后，必须 立即 检查error是否为nil。严禁使用 _ 忽略错误。(The "How") 怎么做:遵循 if err != nil 的标准Go模式。示例:package services

import (
	"encoding/json"
	"fmt"
	"net/http"
)

type ApiResponse struct {
	// ... 字段定义
}

// 函数签名明确表示可能失败
func FetchData(url string) (*ApiResponse, error) {
	resp, err := http.Get(url)
	// 1. 立即检查网络错误
	if err != nil {
		// 使用 fmt.Errorf 和 %w 来包装错误，保留原始错误上下文
		return nil, fmt.Errorf("failed to make HTTP request: %w", err)
	}
	defer resp.Body.Close()

	// 2. 检查非 2xx 的HTTP状态码
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("received non-200 status code: %d", resp.StatusCode)
	}

	var data ApiResponse
	// 3. 立即检查JSON解码错误
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, fmt.Errorf("failed to decode JSON response: %w", err)
	}

	// 只有当所有步骤都成功时，才返回数据和 nil 错误
	return &data, nil
}
(The "Why") 为什么:Go语言在设计上刻意避开了try/catch风格的异常处理。它认为错误是程序控制流的正常一部分，而不是意外。将error作为一个普通的返回值，强制 程序员在每个可能失败的步骤去思考和处理错误路径。这种 显式错误处理 的哲学，虽然代码看起来有些重复，但它极大地提高了代码的健壮性和可预测性。当一个错误发生时，它的处理逻辑就在代码的旁边，非常清晰，不会像异常那样可能跳跃到调用栈很远的地方被一个通用的catch块捕获。%w 动词（Go 1.13+）用于错误包装，它保留了原始错误的完整调用链，便于根源问题的诊断。规则 4.3: 【强制执行】模块化 - 使用小接口和明确的包(The "What") 做什么:定义小而专注的接口（通常只包含一两个方法）。代码按功能组织到不同的包（package）中，包名应清晰地描述其职责。(The "How") 怎么做:示例:// package llm: 定义与LLM交互的接口和实现
package llm

// 定义一个小接口
type Generator interface {
    Generate(prompt string) (string, error)
}

// --- 在另一个文件或包中 ---

// package search: 定义搜索功能的接口和实现
package search

type Fetcher interface {
    Fetch(query string) ([]string, error)
}

// --- 在业务逻辑包中 ---

// package workflow: 编排业务流程
package workflow

import (
	"agent/llm"
	"agent/search"
)

// Workflow 结构体依赖于接口，而不是具体实现
type Workflow struct {
    generator llm.Generator
    fetcher   search.Fetcher
}

// NewWorkflow 是一个构造函数，用于依赖注入
func NewWorkflow(g llm.Generator, f search.Fetcher) *Workflow {
    return &Workflow{generator: g, fetcher: f}
}

func (w *Workflow) Run(query string) (string, error) {
    // ... 使用 w.fetcher 进行搜索
    // ... 使用 w.generator 生成最终答案
    return "workflow result", nil
}
(The "Why") 为什么:Go推崇“组合优于继承”，而小接口是实现组合的关键。在Go中，类型是隐式地满足接口的（如果一个类型实现了接口的所有方法，它就自动满足该接口），这被称为 结构化类型（Structural Typing）。这与Java的显式implements不同。小接口使得这种隐式满足变得非常容易，极大地促进了代码的解耦。Workflow 不关心它得到的是一个真实的OpenAI生成器还是一个测试用的模拟生成器，只要对方有Generate(string) (string, error)方法即可。这种设计模式使得Go代码非常容易进行单元测试（通过注入mock实现）和功能扩展，是Go语言设计的精髓之一。