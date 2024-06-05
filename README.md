# EC2 を起動したり停止したりする Lambda Function

https://zenn.dev/ndjndj/articles/9ab0f2ff5756aa
https://zenn.dev/ndjndj/articles/acd0060dcc4d03

ローカル PC での開発と違ってサーバーを立てているわけですからお金がかかります。
節約したいので、サーバーを使うときだけ起動して使わないときは停止しておきたいです。
マネジメントコンソールから操作することができますが、ログインや画面を移動するのがめんどくさいし、停止するのを忘れそうです。

なので、EC2 を起動/停止する Lambda Function を作成します。
最終的には、API 化し、API Key を設定して外部から呼び出せるようにするのと、スケジュールを設定して特定時間になったら停止できるようにします。

# 流れ
- 起動/停止したい EC2 インスタンスの ID を控える
- Lambda Function をつくる
    - Function をつくる
    - コードを書く
    - EC2 インスタンス ID を環境変数として設定する
    - Lambda Function の権限に EC2 を操作できるロールをアタッチする
- 確認

EC2 インスタンスは任意のものを使用してください。なければ作成してください

# 起動/停止したい EC2 インスタンスの ID を控える
まずは起動/停止したい EC2 インスタンスの ID を控えます。
マネジメントコンソールから EC2 のページまで行って任意のインスタンス ID をどこかメモに残しておきます。

![](https://storage.googleapis.com/zenn-user-upload/9443e571b9cf-20240605.png)

# Lambda Function をつくる
次は EC2 を起動/停止できる Lambda Function を作成します。

## Function をつくる
ランタイムは Python 3.12 を使用します。

![](https://storage.googleapis.com/zenn-user-upload/865bed6ed535-20240605.png)

実行ロールはとりあえず新しいロールを作成していますが、後述するロールをここで作成しても構いません。
詳細設定に関しては全部チェックいれなくて大丈夫です。

## コードを書く
とりあえずコード全文を以下に記します。

```py
import boto3
import json
import os 
import sys
from datetime import datetime, date
from decimal import Decimal

region = "ap-northeast-1"
instances = [os.getenv("INSTANCE_ID")]
ec2 = boto3.client("ec2", region_name=region)

UNDEFINED_STATUS = {"Code": -1, "Name": "Undefined"}

def desc_status_ec2():
    ec2_instance = ec2.describe_instances(
        Filters=[{"Name": "instance-id","Values": instances}]
    )
    ec2_status = ec2_instance \
        .get("Reservations", [{}])[0] \
        .get("Instances", [{}])[0] \
        .get("State", UNDEFINED_STATUS)
    
    return ec2_status 

def lambda_handler(event, context):
    status_code = 200
    body = {}
    try:
        query = event.get("queryStringParameters", {}) 
        if query == None:
            query = {}
        action = query.get("action", "check")
        
        if action == "check":
            ec2_status = desc_status_ec2()
            body = ec2_status
        elif action == "start":
            ec2_status = ec2.start_instances(InstanceIds=instances)
            body = ec2_status \
                .get("StartingInstances", [{}])[0] \
                .get("CurrentState", UNDEFINED_STATUS)
        elif action == "stop":
            ec2_status = ec2.stop_instances(InstanceIds=instances)
            body = ec2_status \
                .get("StoppingInstances", [{}])[0] \
                .get("CurrentState", UNDEFINED_STATUS)
        
    except Exception as e:
        exc_type, _, exc_tb = sys.exc_info()
        print("internal error %s %s: %s" % (exc_tb.tb_lineno, exc_type, e))
        status_code = 500
        body = {
            'message': 'Internal Server Error', 
            'details': "internal error %s %s: %s" % (exc_tb.tb_lineno, exc_type, e)
        }
        
    return {
        'statusCode': status_code,
        'body': json.dumps(body, ensure_ascii=False)
    }
```

### コードの解説
AWS リソースの操作には公式の SDK である boto3 を使用します。

https://aws.amazon.com/jp/sdk-for-python/

まずは EC2 インスタンスのインスタンス ID と boto3 の EC2 を操作する API を使う準備をします。

```
instances = [os.getenv("INSTANCE_ID")]
ec2 = boto3.client("ec2", region_name=region)
```

EC2 インスタンスの起動と停止は boto3 で提供している API を使用すればいいので楽ちんです。
ついでに起動も停止もしない現在の状態を取得する関数も作ります。

```py
# EC2 起動
ec2_status = ec2.start_instances(InstanceIds=instances)

# EC2 停止
ec2_status = ec2.stop_instances(InstanceIds=instances)
```

```py
# 起動状態の確認
def desc_status_ec2():
    ec2_instance = ec2.describe_instances(
        Filters=[{"Name": "instance-id","Values": instances}]
    )
    ec2_status = ec2_instance \
        .get("Reservations", [{}])[0] \
        .get("Instances", [{}])[0] \
        .get("State", UNDEFINED_STATUS)
    
    return ec2_status

ec2_status = desc_status_ec2()
```

https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2/client/start_instances.html
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2/client/stop_instances.html
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2/client/describe_instances.html

今回の Lambda Function では、渡されるパラメータによって、状態確認/起動/停止を分岐できるようにしています。

### 取得しているレスポンスについて
今回のコードでは、レスポンスから起動/停止直後の EC2 インスタンスのステータスを取得しています。
ステータスコードと名称を取得できます。
各ステータスコードは以下のように定義されており、マネージメントコンソールから確認できる、「インスタンスの状態」と対応しています。

https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2/client/describe_instances.html

>instance-state-code - The state of the instance, as a 16-bit unsigned integer. The high byte is used for internal purposes and should be ignored. The low byte is set based on the state represented. The valid values are: 0 (pending), 16 (running), 32 (shutting-down), 48 (terminated), 64 (stopping), and 80 (stopped).

|Code|Name         |インスタンスの状態|
|----|-------------|-----------------|
|0   |pending      |保留中           |
|16  |running      |実行中           |
|32  |shutting-down|シャットダウン中  |
|48  |terminated   |終了済み          |
|64  |stopping     |停止中           |
|80  |stopped      |停止済み         |

今回の利用用途で重要なのは、0(保留中), 16(実行中), 64(停止中), 80(停止済み) でしょうか。
それ以外の、48(終了済み)とかが出てたら異常ですね。

また、レスポンスが気になる人は先述した API リファレンスを参照したり Function の戻り値を以下のように変更して確認してみるのもいいと思います。

```py
import boto3
import json
import os 
import sys
from datetime import datetime, date
from decimal import Decimal

region = "ap-northeast-1"
instances = [os.getenv("INSTANCE_ID")]
ec2 = boto3.client("ec2", region_name=region)

UNDEFINED_STATUS = {"Code": -1, "Name": "Undefined"}

def desc_status_ec2():
    ec2_instance = ec2.describe_instances(
        Filters=[{"Name": "instance-id","Values": instances}]
    )
    ec2_status = ec2_instance \
        .get("Reservations", [{}])[0] \
        .get("Instances", [{}])[0] \
        .get("State", UNDEFINED_STATUS)
    
    return ec2_instance

def lambda_handler(event, context):
    status_code = 200
    body = {}
    try:
        query = event.get("queryStringParameters", {}) 
        if query == None:
            query = {}
        action = query.get("action", "check")
        
        if action == "check":
            body = desc_status_ec2()
        elif action == "start":
            body = ec2.start_instances(InstanceIds=instances)
        elif action == "stop":
            body = ec2.stop_instances(InstanceIds=instances)
               
    except Exception as e:
        exc_type, _, exc_tb = sys.exc_info()
        print("internal error %s %s: %s" % (exc_tb.tb_lineno, exc_type, e))
        status_code = 500
        body = {
            'message': 'Internal Server Error', 
            'details': "internal error %s %s: %s" % (exc_tb.tb_lineno, exc_type, e)
        }
        
    return {
        'statusCode': status_code,
        'body': json.dumps(body, ensure_ascii=False, default=defined_handler)
    }

def defined_handler(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return obj
```


## EC2 インスタンス ID を環境変数として設定する
先ほど控えた EC2 インスタンス ID を Lambda Function の環境変数に設定します。
設定 -> 環境変数から変更できるはずです。

![](https://storage.googleapis.com/zenn-user-upload/363a7dae9a71-20240605.png)

## Lambda Function の権限に EC2 を操作できるロールをアタッチする
最後に、EC2 を操作できる権限をアタッチします。
設定 -> アクセス権限から IAM ロールを変更できる画面に移動できるはずです。
下記のようなインラインポリシーを作成して Lambda ロールにアタッチします。

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "ec2:Describe*",
                "ec2:Start*",
                "ec2:Stop*"
            ],
            "Resource": "*"
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogStream",
                "logs:CreateLogGroup",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
```

# 確認
適当なテストイベントを作成して作成した Lambda Function の動作確認をします。
ここでは、後ほど API Gateway を用いて API 化するので apigateway-aws-proxy テンプレートを使用しています。

"queryStringParameters" の "action" を切り替えて、レスポンスとマネジメントコンソール上の EC2 ステータスが一致しているかどうかを確認していきます。
ただ、stopping と pending ステータスに関しては一瞬で遷移する場合があるのであくまで、望む方向に EC2 ステータスが変化しているかどうかを確認しています。

# 最後に
以上で、EC2 の起動/停止/状態確認を行うことができる Lambda Function を構築することができました。とはいえ、現在の状態では AWS のマネジメントコンソールにログインし、Lambda の画面まで移動する必要があるので、当初の目的を達成できたとは言えません。
なので、次回以降で API Key を設定して API Gateway と連携させて外部から起動状態を変更できるようにしたり、EventBridge を使用して定期実行できるようにしたりしていきたいと思います。

**API 化する記事を書きました**
https://zenn.dev/ndjndj/articles/61d817443adc28

# 参考
https://aws.amazon.com/jp/sdk-for-python/
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2/client/start_instances.html
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2/client/stop_instances.html
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2/client/describe_instances.html
https://qiita.com/YK0214/items/59bc0e5ae89f68af74b3