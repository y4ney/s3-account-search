#!/usr/bin/env python
import sys
from argparse import ArgumentParser
from typing import Tuple, Optional

import boto3 as boto3
from aws_assume_role_lib import assume_role
from botocore.exceptions import ClientError


def run():
    # 解析命令行参数
    parser = ArgumentParser()
    parser.add_argument(
        "--profile", 
        help="源配置文件",
    )
    parser.add_argument(
        "role_arn",
        help="要扮演的角色的 ARN。此角色应具有 s3:GetObject 和（或）s3:ListBucket 权限",
    )
    parser.add_argument(
        "path", 
        help="用于测试的 s3 存储桶或存储桶（路径）",
    )
    args = parser.parse_args()
    # 使用 boto3 库创建一个 AWS 会话（Session）对象。
    # boto3 是用于与 AWS 服务进行交互的 Python 库。
    # 这个会话对象将使用指定的配置文件进行身份验证和授权。
    session = boto3.Session(profile_name=args.profile)
    bucket, key = to_s3_args(args.path)
    role_arn = args.role_arn

    # 尝试在无任何限制的情况下访问存储桶
    if not can_access_with_policy(session, bucket, key, role_arn, {}):
        print(f"{role_arn} 无法访问 {bucket}", file=sys.stderr)
        exit(1)

    print("开始搜索（这可能需要一些时间）")
    digits = ""
    # 进行 12 次迭代，避免无限循环
    # 通过两层循环尝试 0 - 9 的数字组合，
    # 每次生成一个 AWS 策略并检查是否可以使用该策略访问存储桶。
    # 如果可以，记录找到的数字并继续下一轮搜索。
    for _ in range(0, 12):
        for i in range(0, 10):
            test = f"{digits}{i}"
            policy = get_policy(test)
            if can_access_with_policy(session, bucket, key, role_arn, policy):
                print(f"找到：{test}")
                digits = test
                break
    if len(digits) < 12:
        print("出了点问题，我们未能找到全部 12 位数字")
        exit(1)


def get_policy(digits: str):
    """
    生成一个 AWS 策略，该策略允许访问指定的 AWS 账户中的资源。
    :param digits: 要匹配的 AWS 账户的前 12 位数字。
    :return: 一个包含 AWS 策略的字典。
    """
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowResourceAccount",
                "Effect": "Allow",
                "Action": "s3:*",
                "Resource": "*",
                "Condition": {
                    "StringLike": {"s3:ResourceAccount": [f"{digits}*"]},
                },
            },
        ],
    }


def can_access_with_policy(
    session: boto3.session.Session,
    bucket: str,
    key: Optional[str],
    role_arn: str,
    policy: dict,
):
    """
    尝试使用指定的策略访问指定的存储桶或存储桶中的对象。
    :param session: 用于创建 AWS 客户端的 boto3 会话对象。
    :param bucket: 要访问的存储桶名称。
    :param key: 要访问的存储桶中的对象键（如果没有则为 None）。
    :param role_arn: 要扮演的角色的 ARN。
    :param policy: 要应用的策略。
    :return: 如果可以访问存储桶或对象，则返回 True；否则返回 False。
    """
    # 根据是否提供 policy 参数，使用不同的方式扮演指定的 IAM 角色。
    if not policy:
        assumed_role_session = assume_role(session, role_arn)
    else:
        assumed_role_session = assume_role(session, role_arn, Policy=policy)

    # 使用扮演的角色创建一个 S3 客户端对象。
    s3 = assumed_role_session.client("s3")
    # 如果提供了 key 参数，尝试使用 head_object 方法访问指定的 S3 对象。
    if key:
        try:
            s3.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "403":
                pass  # 尝试下一个操作
            else:
                raise
    # 如果没有提供 key 参数，尝试使用 head_bucket 方法访问指定的 S3 存储桶。 
    try:
        s3.head_bucket(Bucket=bucket)
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "403":
            pass  # 继续执行默认返回 False 的操作
        else:
            raise
    return False


def to_s3_args(path: str) -> Tuple[str, Optional[str]]:
    """
    从 s3://bucket/key 格式的路径中提取存储桶名称和对象键。
    :param path: 输入的 s3 路径，格式可以是 s3://bucket/key 或者 bucket/key。
    :return: 一个元组，第一个元素是存储桶名称，第二个元素是对象键，如果没有对象键则为 None。
    """
    if path.startswith("s3://"):
        path = path[5:]
    assert path, "未提供存储桶名称"

    parts = path.split("/")
    if len(parts) > 1:
        return parts[0], "/".join(parts[1:])
    # 恰好只有一个部分
    return parts[0], None


if __name__ == "__main__":
    run()
