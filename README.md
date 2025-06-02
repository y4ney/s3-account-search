# S3 账户搜索

此工具可让您查找 S3 存储桶所属的账户 ID。

要使此工具正常工作，您至少需要具备以下权限之一：

- 从存储桶下载已知文件的权限 (`s3:getObject`)。
- 列出存储桶内容的权限 (`s3:ListBucket`)。

此外，您还需要一个可以扮演的角色，该角色需具备您正在检查的存储桶的（其中一项）上述权限。

更多背景信息可在 [Cloudar 博客](https://cloudar.be/awsblog/finding-the-account-id-of-any-public-s3-bucket/) 中找到。

## 安装

此软件包可在 PyPI 上获取，例如，您可以使用以下命令之一（建议使用 pipx）

```shell
pipx install s3-account-search
pip install s3-account-search
```

## 使用示例

```shell
# 使用存储桶
s3-account-search arn:aws:iam::123456789012:role/s3_read s3://my-bucket

# 使用对象
s3-account-search arn:aws:iam::123456789012:role/s3_read s3://my-bucket/path/to/object.ext

# 您也可以省略 s3://
s3-account-search arn:aws:iam::123456789012:role/s3_read my-bucket

# 或者从指定的源配置文件开始
s3-account-search --profile source_profile arn:aws:iam::123456789012:role/s3_read s3://my-bucket
```

## 工作原理

存在一个 IAM 策略条件 `s3:ResourceAccount`，它用于授予对指定账户（或账户集合）中的 S3 服务的访问权限，同时也支持通配符。通过构建合适的模式，并观察哪些模式会导致拒绝或允许，我们可以逐位发现账户 ID 来确定它。

1. 我们验证使用提供的角色是否可以访问对象或存储桶。
2. 我们再次承担相同的角色，但这次添加一个策略，将我们的访问权限限制为以 `0` 开头的账户中的 S3 存储桶。如果我们的访问被允许，我们就知道账户 ID 必须以 `0` 开头。如果请求被拒绝，我们将第一位数字改为 `1` 再次尝试。我们不断递增，直到请求被允许，从而找到第一位数字。
3. 我们对每一位数字重复这个过程。使用已经发现的数字作为前缀。例如，如果第一位数字是 `8`，我们测试以 `80`、`81`、`82` 等开头的账户 ID。

## 开发

我们使用 Poetry 来管理这个项目。

1. 克隆这个仓库。
2. 运行 `poetry install`。
3. 使用 `poetry shell` 激活虚拟环境（您也可以使用 `poetry run $command`）。

### 发布新版本到 PyPI

1. 编辑 `pyproject.toml` 以更新版本号。
2. 提交版本号的变更。
3. 运行 `poetry publish --build`。
4. 推送到 GitHub。
5. 在 GitHub 上创建一个新的版本。

## 可能的改进

- 我们可以使用类似二分查找的算法，而不是逐位检查。例如，以下条件等同于 `s3:ResourceAccount < 500000000000`

  ```json
  "Condition": {
    "StringLike": {"s3:ResourceAccount": [
      "0*", "1*", "2*", "3*", "4*",
    ]},
  },
   ```

- 同样地，通过并行检查每个位置的多个数字，有可能提高速度（使用这种方法时，存在被 STS 限流的小风险）。

在实践中，这个工具在大多数情况下应该足够快。
