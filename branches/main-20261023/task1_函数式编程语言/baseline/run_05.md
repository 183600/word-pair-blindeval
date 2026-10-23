# 任务1 函数式编程语言 | 条件: baseline | 第 5 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 114.02s | **tokens:** 92/1214

---

# 函数式编程语言设计：Lumen（流明）

## 一、设计理念

Lumen 的设计目标：**让数学般的优雅与工程实践共存**。

核心原则：
1. **默认纯函数，副作用显式化**
2. **代数数据类型 + 模式匹配是一等公民**
3. **效果系统（Effect System）替代 Monad 栈**
4. **零成本抽象，可编译到原生代码**
5. **错误即值，永不抛异常**

---

## 二、基本语法

```lumen
-- 变量绑定（默认不可变）
let x = 42
let name = "Lumen"

-- 可变绑定需要显式声明
let mut counter = 0

-- 函数定义
fn add(a: Int, b: Int) -> Int = a + b

-- 类型可推导，注解可选
fn square(x) = x * x

-- 管道操作符
let result =
    [1, 2, 3, 4, 5]
    |> List.filter(is_even)
    |> List.map(square)
    |> List.sum        -- 20
```

## 三、类型系统

### 代数数据类型

```lumen
type Shape =
    | Circle(radius: Float)
    | Rect(width: Float, height: Float)
    | Point

-- 泛型
type Option<T> =
    | Some(T)
    | None

type Result<T, E> =
    | Ok(T)
    | Err(E)
```

### 模式匹配（穷尽性检查）

```lumen
fn area(shape: Shape) -> Float =
    match shape
    | Circle(r)   => 3.14159 * r * r
    | Rect(w, h)  => w * h
    | Point       => 0.0

-- 守卫与嵌套解构
fn describe(pair: (Int, Option<String>)) =
    match pair
    | (0, _)            => "zero"
    | (n, Some(s)) if n > 0 => "positive with {s}"
    | (_, None)         => "missing"
```

### 行多态记录（Structural Records）

```lumen
let user = { name: "Alice", age: 30 }

fn greet(person: { name: String, ..rest }) -> String =
    "Hello, {person.name}!"
```

## 四、效果系统（核心创新）

副作用写在类型签名里，编译器强制处理：

```lumen
-- 效果声明在方括号中
fn read_config(path: String) -> Result<Config, IOError> [IO] = ...

fn log(msg: String) -> Unit [Console] = ...

fn compute(x: Int) -> Int = x * 2   -- 纯函数，无效果标注

-- 效果组合与处理（handler）
fn main() -> Unit [IO, Console] =
    let config = handle read_config("app.toml")
        | Err(e) => default_config
        | ok     => ok
    log("loaded: {config.name}")
```

效果是可以**被拦截和替换**的，测试时注入 mock：

```lumen
test "config loading" =
    with fake_io({ "app.toml" => test_data }) in
        assert read_config("app.toml") == expected
```

## 五、并发模型：结构化并发 + 不可变数据

```lumen
-- 轻量级任务，数据不可变所以共享零成本
async fn fetch_all(urls: List<String>) -> List<Response> [Net] =
    urls
    |> List.par_map(fetch)      -- 自动并行
    |> await_all

-- 通道通信
let (tx, rx) = Channel.new<Int>()
spawn { tx.send(42) }
let val = rx.recv()
```

## 六、错误处理：无异常

```lumen
fn divide(a: Float, b: Float) -> Result<Float, DivError> =
    if b == 0.0 then Err(ZeroDivision) else Ok(a / b)

-- ? 操作符自动传播错误
fn calculate() -> Result<Float, DivError> =
    let x = divide(10.0, 2.0)?
    let y = divide(x, 0.0)?   -- 提前返回 Err
    Ok(y + 1.0)
```

## 七、模块系统

```lumen
module Geometry exposing (Shape, area, perimeter)

import Geometry as Geo
import List exposing (map, filter)   -- 显式导入，无隐式污染
```

## 八、编译与工具链

| 特性 | 说明 |
|------|------|
| 编译目标 | LLVM 原生 / WASM / JS |
| 内存管理 | 编译期所有权分析 + Perceus 引用计数，无 GC 暂停 |
| 格式化 | `lumen fmt` 唯一官方风格，终结风格之争 |
| 包管理 | 内置，语义化版本锁定，确定性构建 |
| 交互环境 | `lumen repl`，支持类型查询 `:type` |

## 九、设计亮点总结

1. **效果系统**：比 Haskell Monad 更直观，比 Rust 生命周期更聚焦副作用
2. **无异常哲学**：所有失败路径在类型中可见
3. **不可变默认 + 编译期优化**：兼顾安全与性能
4. **单一明确的做法**：格式化、包管理、错误处理都有官方答案，降低决策疲劳

想深入哪一部分？比如效果系统的类型推导细节、内存模型，或者写一个完整示例程序？
