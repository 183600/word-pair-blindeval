# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: word_pairs | 第 4 次

**Prompt:** 在回答前面输出200组词，每组有两个词，从这些词获得灵感
设计一个全新的函数式编程语言

**耗时:** 71.1s | **tokens:** 213/6358(推理 2927) | **finish:** stop

---

# 一、200 组词（灵感来源）

雾/灯塔 · 种子/森林 · 潮汐/契约 · 织机/括号 · 琥珀/时间 · 折叠/纸鹤 · 螺旋/递归 · 静默/并行 · 藤蔓/栅栏 · 沙漏/并发
影子/可变 · 蜂巢/递归 · 瓷器/类型 · 回声/延迟 · 根系/模块 · 棱镜/多态 · 雪线/纯度 · 齿轮/惰性 · 灯笼/所有权 · 潮痕/垃圾回收
苔藓/增量 · 断桥/异常 · 沙/作用域 · 藤壶/副作用 · 纸/折叠 · 星图/类型推断 · 沉香/记忆化 · 门槛/守卫 · 窑/编译 · 鹤/代数数据类型
潮汐/状态 · 茧/不可变 · 井/引用透明 · 钥匙/闭包 · 织女/惰性求值 · 孤岛/命名空间 · 桦木/值语义 · 风箱/协程 · 砚/类型类 · 汽笛/信号
沙丘/结构共享 · 极光/宏 · 蜂/数据流 · 巢/接口 · 螺/递归数据结构 · 琥珀/垃圾 · 藤/组合子 · 苔/元编程 · 蕨/展开 · 榛/模式匹配
杉/尾调用 · 桦/柯里化 · 槐/高阶函数 · 榆/偏函数 · 柏/标注 · 松/别名 · 枫/模式守卫 · 柳/流水线 · 桃/不可变集合 · 杏/谓词
梨/单子 · 枣/函子 · 栗/单子组合 · 榛/逆单子 · 榉/效应系统 · 杉木/线性类型 · 云杉/所有权 · 冷杉/借用检查 · 铁杉/生命周期 · 落叶松/逃逸分析
白桦/模式变量 · 黑檀/不透明类型 · 紫檀/编译期求值 · 黄杨/常量折叠 · 榆树/内联 · 梧桐/空安全 · 桑树/错误恢复 · 无花果/结果单子 · 菩提/解 Applicative · 莲/解 Monad
竹/解递归 · 松竹/静态单态化 · 藤本/泛型 · 爬山虎/继承替代 · 常春藤/结构化并发 · 薄荷/热重载 · 迷迭香/增量编译 · 百里香/解释器 · 牛至/编译到寄存器 · 莳萝/JIT
罗勒/类型擦除 · 茴香/管道操作符 · 芝麻/点自由 · 核桃/运算符重载 · 榛子/开放递归 · 杏仁/类型别名 · 腰果/隐式转换 · 开心果/类型转换 · 板栗/模式匹配编译 · 松子/求值顺序
葵花/向量 · 郁金香/生成器 · 风信子/迭代器协议 · 水仙/折叠结构 · 鸢尾/同态 · 薰衣草/缓存 · 雪松/序列化 · 丝柏/热路径 · 圆柏/不可变性 · 刺柏/引用计数
杜松/标记清除 · 冬青/写时复制 · 苦丁/零成本抽象 · 芦荟/编译期常量 · 龙舌兰/宏卫生 · 仙人掌/作用域安全 · 芦苇/弱引用 · 菖蒲/虚调用 · 芍药/内联汇编 · 牡丹/条件编译
兰草/特化 · 蕙兰/类型特化 · 春兰/编译优化 · 建兰/逃逸 · 墨兰/所有权转移 · 玉兰/借用 · 广玉兰/可变性 · 二乔/数据析构 · 虞美人/终结器 · 含羞草/惰性副作用
勿忘我/可重入 · 紫罗兰/纯函数 · 石竹/组合 · 康乃馨/柯里化 · 满天星/高阶抽象 · 车前草/谓词提升 · 蒲公英/共享传播 · 荠菜/优先级 · 马齿苋/中缀 · 苍耳/解析器组合子
狗尾草/DSL · 稗草/布局 · 芦苇荡/注释 · 菱/反射 · 菱角/元数据 · 荸荠/编译期插件 · 芋/单子解析 · 魔芋/序列 · 山药/类型类推导 · 葛/字符串插值
甘薯/字符语法 · 竹芋/可选分号 · 香蕉/幂等 · 芒果/版本 · 菠萝/不动点 · 椰子/全函数 · 油棕/函子 · 棕榈/循环 · 蒲葵/守卫语法 · 蒲草/归约
薏苡/累积折叠 · 苋/映射 · 马唐/过滤器 · 牛筋草/排序 · 雀稗/双向类型 · 苔玉/底层表示 · 藓/字节码 · 孢子/虚拟机 · 菌丝/链接 · 蘑菇/包管理
木耳/模块边界 · 香菇/可见性 · 松茸/特性 · 杏鲍菇/混入 · 金针菇/扩展函数 · 平菇/开放系统 · 竹荪/网络效应 · 牛肝菌/IO 与纯分离 · 青头菌/不可变 IO · 鸡枞/文件系统
松露/权限 · 羊肚菌/加密 · 银耳/状态单子 · 榆耳/无状态 · 灵芝/错误类型 · 雪莲/不可逆 · 雪茶/冻结 · 冰草/持久化链表 · 霜降/终结 · 鹤骨/惰性栈

---

# 二、语言设计：**Lumen（流明）**

> 取自第一组词：**雾 / 灯塔**。口号：*在雾中点灯*——类型系统是你的灯塔。

## 0. 一句话定位

一门**纯函数式内核 + 代数数据类型 + 线性所有权 + 代数效应**的静态强类型语言，用编译器消灭"运行时的惊喜"，用效应行取代"副作用魔法"。

## 1. 设计哲学（来自词对的映射）

| 灵感 | 落到语言里 |
|---|---|
| 雾/灯塔 | 静态类型 + 双向类型检查，错误信息带"光照路径" |
| 茧/不可变、雪线/纯度 | 默认纯函数，值不可变，持久化数据结构 |
| 灯笼/所有权、藤/组合子 | 线性类型管资源，组合子管抽象 |
| 蚕丝/线性类型 | 移动语义 + 借用检查，零 GC 也安全 |
| 蜂巢/递归、螺 | 代数数据类型 + 多路模式匹配 + 结构共享 |
| 沙漏/并发、常春藤 | 结构化并发（作用域即生命周期） |
| 琥珀/时间 | 效应是值、可被 handler 捕获、可被序列化 |
| 窑/编译、极光/宏 | 编译期求值 + 卫生宏 + 静态插件 |
| 雪莲/不可逆、霜降/终结 | 析构、终结器写入函数签名 |

## 2. 语法骨架

- **缩进敏感**，无分号，`{}` 仅用于 do 块
- 绑定用 `=`，模式可作为参数：`map :: (a -> b) -> [a] -> [b]`
- 一切皆函数，**默认柯里化**，点自由是一等公民
- 注释 `//` 与 `/* */`

```lumen
type Shape =
  | Circle(r: f64)
  | Rect(w: f64, h: f64)
  | Empty

area : Shape -> f64
area = fn s => match s {
  Circle(r)  => π * r * r
  Rect(w, h) => w * h
  Empty      => 0.0
}
```

## 3. 类型系统

**代数数据类型 + 记录 + 行多态 + 类型类 + 双向推断**

```lumen
// 记录 row 多态：字段可自由增删
getAge : {age: i32 | r} -> i32
getAge = fn p => p.age

// 多态 + 类型类约束
printAll : (Show a, ∀x. Show x => a) -> [a] -> io<Env, Unit>
printAll = fn xs => each(xs, printLn)
```

- **穷尽性检查**：漏一个分支 = 编译错误（不运行就报错）
- **空安全**：无 `null`，用 `Option[T] = None | Some(T)`；解包需显式 `let Some(x) = opt else { ... }`
- **渐进类型**：`Any`/`as` 是显式、有边界的逃生舱，且带来源标注

## 4. 线性类型与所有权（灯笼/所有权）

资源类型默认**线性**：必须恰好消费一次。

```lumen
with File("log.txt", Read) { f =>            // f 离开 with 块必须用掉
  lines = f.readAll()                        // 消费 f
  println(lines.length)                      // 用过了 → OK
} // 若 f 未被消费 → 编译错误 "linear value escapes"
```

- `Ref` 是**仿射**的（可用 0 或 1 次，但至多一次）
- 有 `move`、`&borrow`、`drop`，配合逃逸分析决定栈/堆
- 无 `unsafe`，底层访问必须走被标注的 `@intrinsic`

## 5. 效应系统（琥珀/时间、潮汐/状态）

函数类型带一行**效应行**：`f : A -> eff<E, B>`

```lumen
sum : [i32] -> pure<i32>
first : [T] -> throw<E, T>
pop   : Ref<[T]> -> state<Env, [T], T>
ask   : Query -> ask<E, Answer>
```

- 内置效应：`pure / io / state / throw / ask / yield(并发) / log`
- do-notation 自动降级为组合子

```lumen
open Lumen.IO : io<Env, Unit>
open Lumen.State : state<Env, Ref<i32>, Unit>

main : io<Env, Unit>
main = do {
  r <- Ref.new(0)
  bump(r)                       // 借用，不转移所有权
  n <- readLine()               // io
  guard(n != "") else throw Empty
  printLn("sum={r.value}, you said {n}")
}
```

## 6. 代数效应与结构化并发（沙漏/并发）

**effect 声明** + **handler** 捕获深栈调用：

```lumen
effect Log = log { emit: Str -> Unit }

traced : fn f => handle (f()) using Log {
  emit = fn s => println("[L] {s}")
  ret   = fn x => x
}

main = traced do { emit("start"); work(); emit("done") }
```

并发基于 **yield 效应**（绿色线程/协程）：

```lumen
results = par {
  spawn fetch(urls[0]),
  spawn fetch(urls[1]),
  spawn fetch(urls[2]),
} collect                        // 作用域结束自动 join/取消，可指定超时
```

## 7. 终止性与安全性检查（雪茶/冻结）

- **全函数性检查**：拒绝明显发散的递归
  ```lumen
  loop = fn i => loop(i + 1)   // error: not productive
  ```
- **尾调用保证**，递归深度不炸栈
- 溢出、越界、除零在 `safe` 默认层被捕获为 `Result`，`unsafe` 块需标注

## 8. 编译期求值与卫生宏（窑/编译、极光/宏）

```lumen
derive[Show, Eq] type Point = { x: f64, y: f64 }

inline fact = { @compile 20 }              // 编译期展开为常量表

macro unless c b = quote {
  if !(quoteExpr c) { quoteExpr b }
}
```

- **卫生**：作用域卫生 + 解析阶段卫生（pattern hygiene）
- **阶段一致（stage consistency）**：quote/splice 有阶段检查，`stage1/stage2` 无标记化代码
- 反射只在编译期开放（型别 → 代码 → AST → 再编译）

## 9. 不可变数据结构与性能（葵花/向量、蒲公英/共享）

- 持久化：向量化列表、哈希数组映射树、路径压缩元组
- **零成本抽象**：泛型单态化 + 跨模块内联 + 逃逸分析
- 线性数据无引用计数开销，非线性数据可选 ARC / 分代 GC
- `pure` 内核保证无隐藏分配；`purity` 优化 pass 能证明无分配循环

## 10. 工具链

- `lumen check` 双向检查，错误带"灯塔路径"：`--> expected f64, found i32 at Rect.w`
- `lumen repl` 带效应行提示
- `lumen build --emit=llvm`，也可 `--jit`、WASM 后端
- 增量编译靠内容寻址（增量/苔藓）
- 语言服务器：补全、重构、可视化效果行

## 11. 完整示例（把这些词都用上）

```lumen
open Lumen.IO : io<Env, Unit>

type Expr =
  | Num(f64)
  | Add(Expr, Expr)
  | Mul(Expr, Expr)
  | Var(Str)

eval : {env: Map<Str, f64>} -> Expr -> throw<EvalError, f64>
eval = fn e env => match e {
  Num(n)     => n
  Var(k)      => env.lookup(k) else throw (Unknown k)
  Add(l, r)   => eval l env + eval r env
  Mul(l, r)   => eval l env * eval r env
}

pipeline :: [f64] -> [f64]
pipeline = fn xs => xs |> each(λ x => x * 2) |> foldl(0.0, (+))

main = handle (do {
  with File("data.txt", Read) { f =>          // 线性：必须消费
    xs = f.readLines |> map(parseF64)
    pipeline(xs) |> each(printLn)
  }
}) using Log { emit = printLn }
```

## 12. 标准库命名观

`Option` / `Result` / `Either` · `List` / `Vector` / `Map` / `Set`（持久化）
`Effect` / `Handler` · `Task`（结构化并发）· `Resource`（线性 RAII）
`Foldable` / `Functor` / `Monad`（类型类）· `Parse`（解析器组合子/苍耳）

## 13. 路线图

1. v0.1：ADT + 模式匹配 + 柯里化 + 效应行
2. v0.3：线性类型 + 借用检查 + LLVM 后端
3. v0.6：代数效应 + 结构化并发
4. v0.9：卫生宏 + 编译期求值 + 反射
5. v1.0：WASM/自举（用 Lumen 写编译器前半部分）

---

**一句话总结**：Lumen 把"纯度"做成可检查的契约，把"副作用"降格成可被握在手里的数据（效应值），把"资源"交给线性类型，把"并发"圈进作用域——然后用编译器当灯塔，照亮雾里的每一行代码。
