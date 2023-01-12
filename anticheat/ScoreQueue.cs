
using System.Text;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;

internal class ScoreQueue : Queue<ulong>
{
    IModel? _channel = null;

    private string _hostname = "";

    private ushort _port = 0;

    public ScoreQueue(string hostname, ushort port)
    {
        _hostname = hostname;
        _port = port;
    }

    ~ScoreQueue()
    {
        _channel?.Close();
    }

    public void Connect()
    {
        Program.Log($"Creating RabbitMQ connection on {_hostname}:{_port}...", ConsoleColor.Cyan);
        
        IConnection connection = new ConnectionFactory()
        {
            HostName = _hostname,
            Port = _port
        }.CreateConnection();

        Program.Log("RabbitMQ connection successful, creating consumer...", ConsoleColor.Cyan);

        _channel = connection.CreateModel();

        // Create a durable, non-exclusive and non-autodelete queue
        _channel.QueueDeclare(queue: "bpy.anticheat.score_queue",
                               durable: true,
                               exclusive: false,
                               autoDelete: false,
                               arguments: null);

        EventingBasicConsumer consumer = new EventingBasicConsumer(_channel);
        consumer.Received += Received;

        _channel.BasicConsume(queue: "bpy.anticheat.score_queue",
                             autoAck: true,
                             consumer: consumer);

        Program.Log("Consumer successfully created.", ConsoleColor.Cyan);
    }

    private void Received(object? sender, BasicDeliverEventArgs e)
    {
        byte[] body = e.Body.ToArray();
        ulong scoreId = BitConverter.ToUInt64(body);
        Enqueue(scoreId);

        Program.Log($"A new score with ID {scoreId} has been enqueued.");
    }
}