# 接入技能柜

技能柜在本机先做决定。宿主里的模型开口之前，必须把用户的原句交过来。回来的那段文字就是这次的结果。模型只执行它，不再挑选技能，也不再问要不要用技能。

网页 <http://127.0.0.1:8765/> 是给人看柜子的。接入不走这个网页。

## 你要做的事

在模型看到这句话之前：

1. 取出用户的原句。不要拆开，不要先让模型总结。
2. 原句以 `jev-decision:` 开头就停（旧前言留下的 `【技能柜】` 也算）。那是上一轮写进去的，再送一次会重复选择。只在句子中间提到这个词不算。
3. 把原句交给柜，拿到前言。
4. 前言是空的，就按平时那样继续。选择器关着的时候会是空的。
5. 前言不是空的，就把它放在这一轮的开头，然后再让模型说话。

失败时前言会写成：自己做，不要翻技能柜。这时不要再去柜子里找技能。

## 怎么把原句交过来

推荐走前言服务。Hermes、OpenClaw 和 DeepSeek Harness 插件已经是这条路。

没有进程时，在项目根目录用项目里的 Python 启动它：

```bash
.venv\Scripts\python.exe host\preface_worker.py
```

它监听本机一个空闲端口，并把端口写进 `runtime/preface.port`。先看这个文件，再访问 `http://127.0.0.1:<端口>/health`。返回正常再发原句。

```http
POST /preface
Content-Type: application/json

{"task": "用户的原句", "source": "你的宿主名"}
```

返回：

```json
{"preface": "jev-decision: 已选定：docx。用你宿主自己的技能工具读正文，读完照做，不要再挑选。"}
```

必须带本机令牌。服务把令牌写在 `runtime/preface.token`，请求头用 `X-Kit-Token`。没有令牌或令牌不对，前言服务直接拒绝。项目里的 Python 客户端 `host/preface_client.py`、最小示例 `examples/ask_preface.py`，以及 OpenClaw / DeepSeek Harness 插件都会读这个文件。不要把令牌写进仓库。

`source` 只是记在调用记录里的名字，例如 `hermes`、`openclaw`。不要把密钥放进这个请求。

同一个进程里也可以直接调用：

```python
import cabinet

preface = cabinet.host_preface("用户的原句", "你的宿主名")
```

## 前言是什么意思

每段前言都以 `jev-decision:` 开头。它只报选了什么，不再把正文塞进来。

- 写了「自己做」：这次没有技能。模型自己完成，不要打开技能目录，不要再选。
- 写了技能名：这些就是要用的技能。正文不在前言里，用宿主自己的技能工具（或 MCP 的 `get_skill`）读，读完照做，不要改用别的技能。
- 写了插件：按那一句去用指定宿主上的那个插件。插件只在已经装了它的宿主里能跑。柜子不会替你安装，也不会去改那个宿主的配置来启动它。
- 写了「沿用了你对某一句的调整」：这次沿用了以前对很像的那句话做过的增删。

技能正文来自项目里的副本：`skills/<分类>/<技能名>/SKILL.md`。这就是设置里的技能文件夹，路径会显示成这台电脑上的绝对路径。原来的技能目录不会被删。这些副本、本机已安装的插件和 MCP 配置不进公开仓库，每台机器自己搜索或安装。

## 选择是怎么定的

打分的是本机的 jev-decision，权重在 `models/jev/head.json`。它不调用云端。这项优化只覆盖技能、插件和 SKILL.md 的选择。

它只看柜门上的那几项本地活，加上能点名的插件。柜子里其余技能可以浏览，但不是选项。只教模型怎么想的技能不进这道题。

一扇门留下，要同时满足两件事：原句里点了这项的名字，并且这项的分数达到 0.4。没写进权重的插件门，点了名就会留下。点了名字附近写了「不要」「别」「不用」「勿」，这一项去掉；后面又写了「还是用」的，按后面的为准。满足的门全部留下。原句不拆成几段，也没有「最多留三扇」这种上限。没点名的门当作 0 分。

先后顺序是：这次写明的要求和否定，压过你保存过的增删，再压过历史上用过的相近说法，最后才是模型分数。经常用 Word，也不会让这次的「不要 Word」再打开 Word。习惯只在这句话仍然点了名、而且没有否定的时候，才把分数抬到能过线。只问「是什么 / 怎么用 / 有什么用」这类句子，不当成执行请求。

决定会过期。`get_skill` 必须带这次前言末尾的 `decision_id`。号不对时返回「决定已过期。不要改选，也不要猜别的技能。」选过的名字写错则是「没有选定」。过期之后重新把原句交给前言服务，不要猜技能。

独立评测分三份：`tests/eval_cases.json` 是回归集（已经指导过规则修改）；`tests/eval_blind.json` 是未参与调试的句子；记忆第三列只用 `tests/memory_fixture.json`，不读你电脑上的真实记录。训练脚本会拦截前两份里的原句。对比：`.venv\Scripts\python.exe -m host.eval_heldout`，盲测加 `--blind`。`python -m host.train_jev` 先在候选文件上评测，回归下降或提问/否定/核心句被破坏就不替换 `head.json`；对比写在 `models/jev/last-train.json`。样本可以比当前权重新。网页上重新训练若被拒绝，会返回原因而不会挂死。

「不要用 PDF，给我论文」按论文请求计分；模型低于 0.4 算漏召回。记忆样本不得与评测原句相同，但要和要对上的评测句成对；n-gram 覆盖够近才会抬分。「WordPress 建站，不是 Word」按排除 Word 计，不打开建站插件。

插件没有写进权重文件时，只要原句点了它的名字，也会留下。

MCP 不在这道题里。设置页和 MCP 页上的开关、删除、添加，只改柜子自己的清单，不改 Cursor、Hermes、Codex、OpenClaw 的配置文件，也不保存密钥。

## MCP 只负责读

`get_skill` 不能用来挑选，也不能用来浏览柜子。它只能读取 `decision_id` 对应那一次调用记录里已经选定的技能名。没选中的名字会拒绝。过期的 `decision_id` 会说明决定已过期。

stdio 配置：

把下面两条路径换成你克隆下来的项目目录：

```json
{
  "mcpServers": {
    "jev-skill-kit": {
      "command": "项目目录\\.venv\\Scripts\\python.exe",
      "args": ["项目目录\\mcp_server.py"],
      "env": {"USE_TF": "0", "PYTHONUTF8": "1"}
    }
  }
}
```

宿主如果已经把前言放进这一轮，模型按前言做就够了：前言只报名字，正文用 `get_skill` 按名字读。调用时必须带前言末尾的 `decision_id`，超长正文用 `offset` 续读。前言里没有 `decision_id` 的那种（选择失败、或者写着「自己做」）不要调用它。

## 已经接上的宿主

选择器开着时，Hermes 用 `pre_llm_call`，OpenClaw 用 `before_prompt_build`，DeepSeek Harness 插件用 `agent/pre-step`。它们在模型开口前要这段前言。关掉选择器之后，它们不再把原句交过来。

Hermes 的开口前选择和子代理执行日志需要安装本项目的 Hermes 插件。在项目根目录运行 `python -m host.hermes_plugin.install`；它在 `~/.hermes/plugins/jev-skill-kit` 写入一个指向当前项目代码的薄入口，后续更新项目代码不必再复制插件。桌面端和 TUI 还需要 `host.hermes_plugin.install.install_shell_hooks` 把四个 shell hook 写入 Hermes 的 `config.yaml`。本机 Hermes 0.21.0 对子代理只提供共用的思考强度，因此可用 `host.hermes_core_patch.install` 给每个子任务增加独立的 `reasoning_effort`；安装器会保存 `delegate_tool.py.jev.bak`，可用 `host.hermes_core_patch.undo` 恢复。派遣开关打开后，插件和 shell hook 会在 `delegate_task` 执行前给没有明确强度的子任务补上初始规则判断；用户或宿主明确写的强度保持不变。`subagent_start` / `subagent_stop` 会把真实创建、完成事件和实际强度记在网页「派遣」页。此强度判断目前是规则策略，还不是训练好的 JEV 权重。修改后需重新启动 Hermes 才能让已有进程加载新代码。

DeepSeek Harness 可以当插件，也可以当 MCP，两种形式可以一起用。Electron 的 `desktop` profile 不能走 CLI 的 `dsh plugin add`。在 GUI 里：设置 → 插件 → 添加插件，填本机绝对路径 `项目目录\host\harness_plugin`，然后重启 App 并开新会话。安装是**拷贝**：插件被复制成 `profiles\desktop\node_modules\dsh-jev-skill-kit`，之后改项目里的 `host\harness_plugin\index.js` 不会影响那份副本，重启 App 也不会重新复制。所以要么改完重新安装，要么把 profile 的依赖从 `file:项目目录\host\harness_plugin` 改成 `link:项目目录\host\harness_plugin`（`node_modules` 里那份跟着指向项目目录）。改成 link 之后，改完只需重启 App 即生效。不要把 `cordis.patch.yml` 的 `insert.name` 写成 `index.js` 的绝对路径——加载器要的是已经装进该 profile 的包名 `dsh-jev-skill-kit`。其它 profile 可以用：

```bash
dsh plugin add 项目目录\host\harness_plugin
```

Codex 把下面这段加进 `~/.codex/config.toml` 的 MCP 列表，DeepSeek Harness 也可以把同一组绝对路径写进它的 MCP 配置（Harness 要求 `command` 是绝对路径）。MCP 只补读已经选定的技能。

```toml
[mcp_servers.jev-skill-kit]
command = "项目目录\\.venv\\Scripts\\python.exe"
args = ["项目目录\\mcp_server.py"]
```

Cursor 没有接这条前言。不要假设它会先问柜子。

打开网页不会改 Hermes 或 OpenClaw 的配置。只有在设置里保存选择器开关时才会同步那两项 MCP。

## 不要做的事

- 不要让模型自己决定用哪份技能。
- 不要把一句话拆成几个小任务再分别来问。
- 不要用 MCP 的工具列表当技能目录。
- 不要把插件说明写进另一个宿主。一个插件只在装了它的那个宿主里执行。
- 不要为了接入去改 `models/jev/head.json`，也不要改介绍视频和已经复制进来的技能正文。
