import logging
import boto3
from botocore.exceptions import ClientError
from rich import print
from rich.logging import RichHandler
from rich.console import Console
from rich.table import Table

FORMAT = "%(name)s - %(message)s "
LOGLEVEL = ['NOTSET', 'DEBUG', 'INFO', 'WARNING']
logging.basicConfig(format=FORMAT, level=LOGLEVEL[2], datefmt='%m/%d/%Y %I:%M:%S %p', handlers=[RichHandler(markup=True)])
logger = logging.getLogger("logger")

class AWSManager:
	def __init__(self, logger:logging.Logger):
		self.ec2_client = boto3.client("ec2")
		self.asg_client = boto3.client("autoscaling")
		self.rds_client = boto3.client("rds")
		self.logger = logger

	def start_ec2_instances(self) -> None:

		try:
			response = self.ec2_client.describe_instances()
			if response["Reservations"]:
				for reservation in response["Reservations"]:
					for instance in reservation["Instances"]:
						if instance['Tags'][0].get('Value') == 'true':
							continue
						instance_name = instance['Tags'][0].get('Value')
						instance_id = instance["InstanceId"]
						self.ec2_client.start_instances(InstanceIds=[instance_id])
						self.logger.info(f"Started EC2 instance {instance_id} ({instance_name})")
			else:
				raise Exception("No EC2 Instance found!")
		
		except Exception as e:
			self.logger.error(e)

	def stop_ec2_instances(self) -> None:

		try:
			response = self.ec2_client.describe_instances()
			if response["Reservations"]:
				for reservation in response["Reservations"]:
					for instance in reservation["Instances"]:
						# because theres two type of instances yet, one is managed manualy, other is managed by asg, in those cases the first key in the tags dict is 'AmazonECSManaged' and we dont wanna manage those by this function
						if instance['Tags'][0].get('Value') == 'true':
							continue
						instance_name = instance['Tags'][0].get('Value')
						instance_id = instance["InstanceId"]
						self.ec2_client.stop_instances(InstanceIds=[instance_id])
						self.logger.info(f"Stopped EC2 instance {instance_id} ({instance_name})")
			else:
				raise Exception("No EC2 instances found!")
		
		except Exception as e:
			self.logger.error(e)

	def start_rds_db(self) -> None:
        # start all RDS instances
		try:
			response = self.rds_client.describe_db_instances()
			if response["DBInstances"]:
				for db_instance in response["DBInstances"]:
					db_instance_id = db_instance["DBInstanceIdentifier"]
					try:
						self.rds_client.start_db_instance(
							DBInstanceIdentifier=db_instance_id
						)
						self.logger.info(f"Started RDS instance {db_instance_id}")
					except ClientError as e:
						if e.response["Error"]["Code"] == "InvalidDBInstanceState":
							self.logger.error(
								f"RDS instance {db_instance_id} cannot be started as it is not in a valid state!"
							)
						else:
							raise
			else:
				raise Exception("No RDS instances found.")
		except Exception as e:
			self.logger.error(e)

	def stop_rds_db(self) -> None:
        # stop all RDS instances
		try:
			response = self.rds_client.describe_db_instances()
			if response["DBInstances"]:
				for db_instance in response["DBInstances"]:
					db_instance_id = db_instance["DBInstanceIdentifier"]
					try:
						self.rds_client.stop_db_instance(
							DBInstanceIdentifier=db_instance_id
						)
						self.logger.info(f"Stopped RDS instance {db_instance_id}")
					except ClientError as e:
						if e.response["Error"]["Code"] == "InvalidDBInstanceState":
							self.logger.error(
								f"RDS instance {db_instance_id} cannot be stopped as it is not in a valid state"
							)
						else:
							raise
			else:
				raise Exception("No RDS instances found.")
		except Exception as e:
			self.logger.error(e)

	def ec2_asg_desired_capacity(self, desired_count: int, min_count: int, max_count: int ) -> None:
		try:
			asg_response = self.asg_client.describe_auto_scaling_groups()
		except Exception as e:
			# Log and raise the error
			self.logger.error(
				f"Error occurred while retrieving Auto Scaling Groups: {e}"
			)
			raise e

		# Loop through each auto scaling group and set the capacity
		for asg in asg_response["AutoScalingGroups"]:
			# Get the current capacity of the auto scaling group
			current_capacity = asg["DesiredCapacity"]

			try:
				# Set the minimum, maximum and desired capacity of the auto scaling group
				self.asg_client.update_auto_scaling_group(
						AutoScalingGroupName=asg["AutoScalingGroupName"],
						MinSize=min_count,
						MaxSize=max_count,
						DesiredCapacity=desired_count,
					)
			except Exception as e:
				self.logger.error(
					f"Error occurred while updating Auto Scaling Group {asg['AutoScalingGroupName']}: {e}"
				)
				raise e
				
			self.logger.info(
				f"Capacity updated for Auto Scaling Group {asg['AutoScalingGroupName']}: from {current_capacity} to {desired_count}"
			)

	def stop_all_resources(self) -> None:
		self.stop_ec2_instances()
		self.stop_rds_db()
		self.ec2_asg_desired_capacity(0,0,0)

	def start_all_resources(self) -> None:
		self.start_ec2_instances()
		self.start_rds_db()
		self.ec2_asg_desired_capacity(0,2,1)

	def check_ec2_status(self) -> Table:
		ec2_response = self.ec2_client.describe_instances()
		# print(ec2_response)
		# Define a table
		table = Table(title="EC2 Instances")
		table.add_column("Instance ID", justify="left", style="cyan")
		table.add_column("Instance Type", justify="left", style="magenta")
		table.add_column("Instance Name", justify="left", style="cyan")
		table.add_column("State", justify="left", style="green")
		# table.add_column("Launch Time", justify="left", style="yellow")
		
		if ec2_response["Reservations"]:
			for reservation in ec2_response['Reservations']:
				for instance in reservation['Instances']:
					for i in instance['Tags']:
						if i.get('Key') == 'Name':
							instance_name = i.get('Value')
					# instance_name = instance['Tags'][0].get('Value')
					instance_id = instance['InstanceId']
					instance_type = instance['InstanceType']
					state = instance['State']['Name']
					# print(f"Instance ID: {instance_id}, Name:{instance_name}[ Type: {instance_type} ], State: {state}")
					table.add_row(instance_id, instance_type, instance_name, state)
		return table
	
	def check_rds_status(self) -> Table:
		rds_response = self.rds_client.describe_db_instances()
		# print(rds_response)
		table = Table(title="RDS Instances")
		table.add_column("DB Instance ID", justify="left", style="cyan")
		table.add_column("DB Instance Class", justify="left", style="magenta")
		table.add_column("Status", justify="left", style="green")
		
		if rds_response["DBInstances"]:
			for db_instance in rds_response["DBInstances"]:
				db_instance_id = db_instance["DBInstanceIdentifier"]
				db_instance_class = db_instance["DBInstanceClass"]
				db_instance_status = db_instance["DBInstanceStatus"]
				# print(f"Database Instance Name: {db_instance_id}[ Class: {db_instance_class} ], State: {db_instance_status}")
				table.add_row(db_instance_id, db_instance_class, db_instance_status)
		return table
	
	def check_asg_status(self) -> Table:
		asg_response = self.asg_client.describe_auto_scaling_groups()
		# print(asg_response)
		table = Table(title="Auto Scaling Groups")
		table.add_column("ASG Name", justify="left", style="cyan")
		table.add_column("Min Capacity", justify="left", style="magenta")
		table.add_column("Max Capacity", justify="left", style="green")
		table.add_column("Desired Capacity", justify="left", style="yellow")

		for asg in asg_response["AutoScalingGroups"]:
			asg_name = asg['AutoScalingGroupName']
			current_min_capacity = asg['MinSize']
			current_max_capacity = asg['MaxSize']
			current_desired_capacity = asg["DesiredCapacity"]
			# print(f"AutoScalingGroup Name: {asg_name}, Minimum Capacity: {current_min_capacity}, Maximum Capacity: {current_max_capacity}, Desired Capacity: {current_desired_capacity}")
			table.add_row(asg_name, str(current_min_capacity), str(current_max_capacity), str(current_desired_capacity))
		return table
	
	def check_status(self) -> None:
		console = Console()

		ec2_table = self.check_ec2_status()
		print(ec2_table)

		rds_table = self.check_rds_status()
		print(rds_table)

		asg_table = self.check_asg_status()
		print(asg_table)

if __name__== "__main__":
	import os
	from rich import print
	from rich.panel import Panel
	from rich.prompt import Prompt
	from rich.progress import Progress, SpinnerColumn, TextColumn
	from time import sleep, time

	awsman = AWSManager(logger)
	console = Console()
	
	def clear_screen():
		os.system("clear" if os.name == "posix" else "cls")

	def show_menu():
		clear_screen()
		
		# table = Table(title="What would you like to do?")
		# table.add_column("Option", justify="center")
		# table.add_column("Description")
		console.print(Panel.fit("[0][bold yellow]Check Status[/]\n[1][bold red]STOP ALL![/]\n[2][bold green]START ALL![/]\n[3]Start EC2 Instances\n[4]Stop EC2 Instances\n[5]Start RDS Instance\n[6]Stop RDS Instance\n[7]Scale AutoScalingGroup Up\n[8]Scale AutoScalingGroup Down",title="[bold magenta]What would you like to do?[/]\n", border_style="cyan"))

	def run_choice(choice):
		if choice == '0':
			clear_screen()
			console.print(Panel.fit("[maroon]Checking status of AWS resources![/]"))
			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
				task = progress.add_task("[bold cyan]Checking Resource(EC2, RDS, ASG) status", total=None)
				awsman.check_status()

		elif choice == '1':
			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
				task = progress.add_task("[bold cyan]Stopping all resources", total=None)
				awsman.stop_all_resources()

		elif choice == '2':
			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
				task = progress.add_task("[bold cyan]Starting all resources", total=None)
				awsman.start_all_resources()  

		elif choice == '3':
			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
				task = progress.add_task("[bold cyan]Starting EC2 Instances", total=None)
				awsman.start_ec2_instances()  

		elif choice == '4':
			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
				task = progress.add_task("[bold cyan]Stopping EC2 Instances", total=None)
				awsman.stop_ec2_instances()  

		elif choice == '5':
			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
				task = progress.add_task("[bold cyan]Starting RDS Instance", total=None)
				awsman.start_rds_db()  

		elif choice == '6':
			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
				task = progress.add_task("[bold cyan]Stopping RDS Instance", total=None)
				awsman.stop_rds_db()  

		elif choice == '7':
			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
				task = progress.add_task("[bold cyan]Scaling Auto Scaling Group up", total=None)
				awsman.ec2_asg_desired_capacity(min_count=0, max_count=1, desired_count=1)

		elif choice == '8':
			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"),transient=True) as progress:
				task = progress.add_task("[bold cyan]Scaling Auto Scaling Group down", total=None)
				awsman.ec2_asg_desired_capacity(min_count=0,max_count=0,desired_count=0)

		console.input("\n[bold magenta]Press Enter to run another task...[/bold magenta]")
	
	while True:
		show_menu()
		choice = Prompt.ask("Enter your choice", default='q').strip().lower()
		if choice == 'q':
			with console.status("[bold green]Exiting", spinner="arrow3") as status:
				sleep(round(time()%1.5,2))
				break
			exit(0)
		run_choice(choice)

	# 	"""switch case, For python >=3.10
	# 	match choice:
	# 		case '1':
	# 			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
	# 				task = progress.add_task("[bold cyan]Stopping all resources", total=None)
	# 				awsman.stop_all_resources()  

	# 		case '2':
	# 			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
	# 				task = progress.add_task("[bold cyan]Starting all resources", total=None)
	# 				awsman.start_all_resources()  

	# 		case '3':
	# 			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
	# 				task = progress.add_task("[bold cyan]Starting EC2 Instances", total=None)
	# 				awsman.start_ec2_instances()  

	# 		case '4':
	# 			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
	# 				task = progress.add_task("[bold cyan]Stopping EC2 Instances", total=None)
	# 				awsman.stop_ec2_instances()  

	# 		case '5':
	# 			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
	# 				task = progress.add_task("[bold cyan]Starting RDS Instance", total=None)
	# 				awsman.start_rds_db()  

	# 		case '6':
	# 			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
	# 				task = progress.add_task("[bold cyan]Stopping RDS Instance", total=None)
	# 				awsman.stop_rds_db()  

	# 		case '7':
	# 			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
	# 				task = progress.add_task("[bold cyan]Scaling Auto Scaling Group up", total=None)
	# 				awsman.ec2_asg_desired_capacity(min_count=0, max_count=1, desired_count=1)

	# 		case '8':
	# 			with Progress(SpinnerColumn("dots"), TextColumn("[progress.description]{task.description}"),transient=True) as progress:
	# 				task = progress.add_task("[bold cyan]Scaling Auto Scaling Group down", total=None)
	# 				awsman.ec2_asg_desired_capacity(min_count=0,max_count=0,desired_count=0)

	# 		case '9':
	# 			with console.status("[bold green]Exiting", spinner="arrow3") as status:
	# 				sleep(1.2)
	# 				exit(0)
	# 	"""