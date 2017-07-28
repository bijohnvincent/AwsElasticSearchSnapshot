# AwsElasticSearchSnapshot
This project is for automatic the snapshot creation of individual indices in AWS Elasticsearch service. 
You can also create a single snapshot that includes all indices in your ES domain.

This solution is based on the AWS documentation 'Working with Manual Index Snapshots (AWS CLI)' (http://docs.aws.amazon.com/elasticsearch-service/latest/developerguide/es-managedomains.html#es-managedomains-snapshots)

Complete the prerequisites in above link before implementing this solution in Lambda.


## IAM Policies
Folllwoing IAM policies are attached to the IAM role given to Lambda function

### AWSLambdaBasicExecutionRole
This is an AWS managed policy just select it from policy list

### EsPermissions
Add this in 'inline policies'
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
                "es:ESHttp*"
            ],
            "Effect": "Allow",
            "Resource": "arn:aws:es:<region>:<AWS account number>:domain/<ES domain name>/*"
        }
    ]
}
```
### SnsPermissions
Add this in 'inline policies'
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "Stmt1498233095000",
            "Effect": "Allow",
            "Action": [
                "sns:Publish"
            ],
            "Resource": [
                "arn:aws:sns:<region>:<AWS account number>:<Sns Topic name>"
            ]
        }
    ]
}
```
## Shceduling snapshots
Create a Rule in AWS cloudWatch Event for scheduling snapshots. 
* Select 'Schedule' and specify a 'Cron Expression' (eg: 05 00 ? * * *)
* In 'Targets', select the Lambda function you created. Recommend to 'Configure version/alias'
* You may leave 'Configure input' as is if you want to create a snapsot of indices together.
* If you have multiple indices, it is recommended to take snapshot separately so that you can resore it individually. To create separate snapshots for each group of indices, select 'Constant (JSON text)' and add your index pattern name as in below format:

{ "backupIndex" : "\<Index pattern\>*" }

eg: { "backupIndex" : "logstash-*" }

eg: { "backupIndex" : "cwl-*" }

eg: { "backupIndex" : ".kibana*" }

* Based on the size of the indices, snapshot will take some time to complete the process in elasticSearch server. So when you are taking snapshots separately, you have to ensure enough time to complete the previous snapshot before initialing snapshot of another index.

