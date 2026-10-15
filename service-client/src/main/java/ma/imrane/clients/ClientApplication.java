package ma.imrane.clients;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
@SpringBootApplication @EnableDiscoveryClient @EnableFeignClients
public class ClientApplication { public static void main(String[] args) {SpringApplication.run(ClientApplication.class,args);} }
