# -*- coding: utf-8 -*-

from opinel.utils import handle_truncated_response, manage_dictionary

from AWSScout2.configs.regions import RegionalServiceConfig, RegionConfig, api_clients
from AWSScout2.utils import ec2_classic



########################################
# RDSRegionConfig
########################################

class RDSRegionConfig(RegionConfig):
    """
    RDS configuration for a single AWS region

    :ivar vpcs:                         Dictionary of VPCs [id]
    :ivar instances_count:              Number of instances in the region
    :ivar parameter_groups:             Dictionary of parameter groups [id]
    :ivar parameter_groups_count:       Number of parameter groups in the region
    :ivar security_groups_count:        Number of security groups in the region
    """

    def __init__(self):
        self.vpcs = {}
        self.instances_count = 0
        self.parameter_groups = {}
        self.parameter_groups_count = 0
        self.security_groups_count = 0


    def parse_instance(self, global_params, region, dbi):
        """
        Parse a single RDS instance

        :param global_params:           Parameters shared for all regions
        :param region:                  Name of the AWS region
        :param instance:                Instance
        """
        vpc_id = dbi['DBSubnetGroup']['VpcId'] if 'DBSubnetGroup' in dbi and 'VpcId' in dbi['DBSubnetGroup'] and dbi['DBSubnetGroup']['VpcId'] else ec2_classic
        instance = {}
        instance['name'] = dbi.pop('DBInstanceIdentifier')
        for key in ['InstanceCreateTime', 'Engine', 'DBInstanceStatus', 'AutoMinorVersionUpgrade',
                    'DBInstanceClass', 'MultiAZ', 'Endpoint', 'BackupRetentionPeriod', 'PubliclyAccessible',
                    'StorageEncrypted', 'VpcSecurityGroups', 'DBSecurityGroups', 'DBParameterGroups',
                    'EnhancedMonitoringResourceArn', 'StorageEncrypted']:
                    # parameter_groups , security_groups, vpc_security_groups
            instance[key] = dbi[key] if key in dbi else None
        # Save
        manage_dictionary(self.vpcs, vpc_id,RDSVPCConfig())
        self.vpcs[vpc_id].instances[instance['name']] = instance


    def parse_snapshot(self, global_params, region, dbs):
        """

        :param global_params:           Parameters shared for all regions
        :param region:                  Name of the AWS region
        :param dbs:                     Snapshot
        :return:
        """
        vpc_id = dbs['VpcId'] if 'VpcId' in dbs else ec2_classic
        snapshot_id = dbs.pop('DBSnapshotIdentifier')
        snapshot = {'arn': dbs.pop('DBSnapshotArn'), 'id': snapshot_id, 'name': snapshot_id, 'vpc_id': vpc_id}
        attributes = [
            'DBInstanceIdentifier',
            'SnapshotCreateTime',
            'Encrypted',
            'OptionGroupName'
        ]
        for attribute in attributes:
            snapshot[attribute] = dbs[attribute] if attribute in dbs else None
        api_client = api_clients[region]
        attributes = api_client.describe_db_snapshot_attributes(DBSnapshotIdentifier = snapshot_id)['DBSnapshotAttributesResult']
        snapshot['attributes'] = attributes['DBSnapshotAttributes'] if 'DBSnapshotAttributes' in attributes else {}
        # Save
        manage_dictionary(self.vpcs, vpc_id,RDSVPCConfig())
        self.vpcs[vpc_id].snapshots[snapshot_id] = snapshot


    def parse_parameter_group(self, global_params, region, parameter_group):
        parameter_group['arn'] = parameter_group.pop('DBParameterGroupArn')
        parameter_group['name'] = parameter_group.pop('DBParameterGroupName')
        api_client = api_clients[region]
        parameters = handle_truncated_response(api_client.describe_db_parameters, {'DBParameterGroupName': parameter_group['name']}, ['Parameters'])['Parameters']
        for parameter in parameters:
            param = {}
            param['value'] = parameter['ParameterValue'] if 'ParameterValue' in parameter else None
            param['source'] = parameter['Source']
            manage_dictionary(parameter_group, 'parameters', {})
            parameter_group['parameters'][parameter['ParameterName']] = param
        # Save
        (self).parameter_groups[parameter_group['name']] = parameter_group


    def parse_security_group(self, global_params, region, security_group):
        """
        Parse a single Redsfhit security group

        :param global_params:           Parameters shared for all regions
        :param region:                  Name of the AWS region
        :param security)_group:         Security group
        """
        vpc_id = security_group.pop('VpcId') if 'VpcId' in security_group else ec2_classic
        manage_dictionary(self.vpcs, vpc_id, RDSVPCConfig())
        security_group['arn'] = security_group.pop('DBSecurityGroupArn')
        security_group['name'] = security_group.pop('DBSecurityGroupName')
        # Save
        manage_dictionary(self.vpcs, vpc_id,RDSVPCConfig())
        self.vpcs[vpc_id].security_groups['name'] = security_group



########################################
# RDSConfig
########################################

class RDSConfig(RegionalServiceConfig):
    """
    RDS configuration for all AWS regions

    :cvar targets:                      Tuple with all RDS resource names that may be fetched
    :cvar config_class:                 Class to be used when initiating the service's configuration in a new region/VPC
    """
    targets = (
        ('instances', 'DBInstances', 'describe_db_instances', False),
        ('snapshots', 'DBSnapshots', 'describe_db_snapshots', False),
        ('parameter_groups', 'DBParameterGroups', 'describe_db_parameter_groups', False),
        ('security_groups', 'DBSecurityGroups', 'describe_db_security_groups', True),
        # TODO ('subnets', 'DBSubnetGroups', 'describe_db_subnet_group', False),
    )
    region_config_class = RDSRegionConfig



########################################
# RDSVPCConfig
########################################

class RDSVPCConfig(object):
    """
    RDS configuration for a single VPC

    :ivar instances:                     Dictionary of instances [id]
    :ivar security_groups:              Dictionary of security groups [name]
    """

    def __init__(self):
        self.instances = {}
        self.security_groups = {}
        self.snapshots = {}



def get_security_groups_info(rds_client, region_info):
    groups = rds_client.describe_db_security_groups()['DBSecurityGroups']
    manage_dictionary(region_info, 'vpcs', {})
    manage_dictionary(region_info['vpcs'], ec2_classic, {})
    manage_dictionary(region_info['vpcs'][ec2_classic], 'security_groups', {})
    manage_dictionary(region_info, 'security_groups_count', 0)
    region_info['security_groups_count'] += len(groups)
    for group in groups:
        region_info['vpcs'][ec2_classic]['security_groups'][group['DBSecurityGroupName']] = parse_security_group(group)

def parse_security_group(group):
    security_group = {}
    security_group['name'] = group['DBSecurityGroupName']
    security_group['description'] = group['DBSecurityGroupDescription']
    security_group['ec2_groups'] = {}
    for grant in group['EC2SecurityGroups']:
        if 'EC2SecurityGroupId' in grant:
            group_id = grant.pop('EC2SecurityGroupId')
        else:
            group_id = '%s-%s' % (grant['EC2SecurityGroupOwnerId'], grant['EC2SecurityGroupName'])
        security_group['ec2_groups'][group_id] = grant
    security_group['ip_ranges'] = {}
    for ip_range in group['IPRanges']:
        cidr = ip_range.pop('CIDRIP')
        security_group['ip_ranges'][cidr] = ip_range
    return security_group
