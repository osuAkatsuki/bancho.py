
using System.Text;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;

namespace anticheat;

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
        _channel.QueueDeclare("bpy.anticheat.score_queue", true, false, false);

        EventingBasicConsumer consumer = new EventingBasicConsumer(_channel);
        consumer.Received += Received;

        _channel.BasicConsume("bpy.anticheat.score_queue", true, consumer: consumer);

        Program.Log("Consumer successfully created.", ConsoleColor.Cyan);
    }

    private void Received(object? sender, BasicDeliverEventArgs e)
    {
        ulong scoreId = BitConverter.ToUInt64(e.Body.ToArray());
        Enqueue(scoreId);

        Program.Log($"[RabbitMQ] A new score with ID {scoreId} has been enqueued.", ConsoleColor.Magenta);
    }
}