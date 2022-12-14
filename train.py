# -*- coding: utf-8 -*-
"""train.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1EJujBqznOMoJeHIrNRV1xRuLvdbWew09
"""

from google.colab import drive #Optional way to load data
drive.mount('/content/drive')
!pip install anndata
import anndata as sc
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
import pandas as pd
import itertools

train_adata = sc.read_h5ad("/content/drive/My Drive/project 1/SAD2022Z_Project1_GEX_train.h5ad")
preprocessed_train = train_adata.layers['counts'].toarray()

i=0
for column in preprocessed_train:
  preprocessed_train[i] = column/max(column)
  i+=1

train_tensor = torch.from_numpy(preprocessed_train)
train_tensor = torch.reshape(train_tensor, (72208,1,5000))

use_gpu = True
latent_dims = 16
num_epochs = 10
capacity = 32
learning_rate = 2e-5
variational_beta = 10

class Encoder(nn.Module):
    def __init__(self):
        super(Encoder, self).__init__()
        c = capacity
        #in : 1 x 5000 x 1
        self.conv1 = nn.Conv1d(in_channels=1, out_channels=c, kernel_size=20, stride=2, padding=1) # out: c x 2492 x 1 
        self.conv2 = nn.Conv1d(in_channels=c, out_channels=c*2, kernel_size=10, stride=2, padding=1) # out: c*2 x 1243 x 1 
        self.conv3 = nn.Conv1d(in_channels=c*2, out_channels=c*2, kernel_size=5, stride=2, padding=1) # out: c*2 x 621 x 1 
        self.fc_mu = nn.Linear(in_features=c*2*621, out_features=latent_dims)
        self.fc_logvar = nn.Linear(in_features=c*2*621, out_features=latent_dims)
            
    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = torch.flatten(x) # flatten batch of multi-channel feature maps to a batch of feature vectors
        x_mu = self.fc_mu(x)
        x_logvar = self.fc_logvar(x)
        return x_mu, x_logvar

class Decoder(nn.Module):
    def __init__(self):
        super(Decoder, self).__init__()
        c = capacity
        self.fc = nn.Linear(in_features=latent_dims, out_features=c*2*621)
        self.conv3 = nn.ConvTranspose1d(in_channels=c*2, out_channels=c*2, kernel_size=5, stride=2, padding=1)
        self.conv2 = nn.ConvTranspose1d(in_channels=c*2, out_channels=c, kernel_size=10, stride=2, padding=1)
        self.conv1 = nn.ConvTranspose1d(in_channels=c, out_channels=1, kernel_size=20, stride=2, padding=1)
            
    def forward(self, x):
        x = self.fc(x)
        x = torch.reshape(x,(capacity*2,621)) # unflatten batch of feature vectors to a batch of multi-channel feature maps
        x = F.relu(self.conv3(x))
        x = F.relu(self.conv2(x))
        x = torch.sigmoid(self.conv1(x)) # last layer before output is sigmoid, since we are using BCE as reconstruction loss
        return x
    
class VariationalAutoencoder(nn.Module):
    def __init__(self):
        super(VariationalAutoencoder, self).__init__()
        self.encoder = Encoder()
        self.decoder = Decoder()
    
    def forward(self, x):
        latent_mu, latent_logvar = self.encoder(x)
        latent = self.latent_sample(latent_mu, latent_logvar)
        x_recon = self.decoder(latent)
        return x_recon, latent_mu, latent_logvar
    
    def latent_sample(self, mu, logvar):
        if self.training:
            # the reparameterization trick
            std = logvar.mul(0.5).exp_()
            eps = torch.empty_like(std).normal_()
            return eps.mul(std).add_(mu)
        else:
            return mu
    
def ELBO_loss(recon_x, x, mu, logvar):
    # recon_x is the probability of a multivariate Bernoulli distribution p.
    # -log(p(x)) is then the pixel-wise cross-entropy.
    # Averaging or not averaging the cross-entropy over all pixels here
    # is a subtle detail with big effect on training, since it changes the weight
    # we need to pick for the other loss term by several orders of magnitude.
    # Not averaging is the direct implementation of the negative log likelihood,
    # but averaging makes the weight of the other loss term independent of the sequence resolution.
    recon_loss = F.cross_entropy(recon_x, x, reduction='sum')
    
    # KL-divergence between the prior distribution over latent vectors
    # and the distribution estimated by the generator for the given sequence.
    kldivergence = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())

    return recon_loss, variational_beta * kldivergence, recon_loss + (variational_beta * kldivergence)
    
vae16 = VariationalAutoencoder()

device = torch.device("cuda:0" if use_gpu and torch.cuda.is_available() else "cpu")
vae16 = vae16.to(device)

optimizer = torch.optim.Adam(params=vae16.parameters(), lr=learning_rate)
for epoch in range(num_epochs):
  vae16.train()
  num_batches = 0

  #Subset of samples to train
  permutated_train_tensor =  torch.tensor(np.random.permutation(train_tensor)[:20000])

  for tensor_batch in permutated_train_tensor:

    tensor_batch = tensor_batch.to(device)

    tensor_batch_recon, latent_mu, latent_logvar = vae16(tensor_batch)
    # reconstruction error
    recon_loss,reg_loss, loss = ELBO_loss(tensor_batch_recon, tensor_batch, latent_mu, latent_logvar)
    # backpropagation
    optimizer.zero_grad()
    loss.backward()
    
    # one step of the optmizer (using the gradients from backpropagation)
    optimizer.step()
    num_batches += 1

torch.save(vae16, 'vae16.pth')

use_gpu = True
latent_dims = 32
num_epochs = 10
capacity = 32
learning_rate = 2e-5
variational_beta = 10

class Encoder(nn.Module):
    def __init__(self):
        super(Encoder, self).__init__()
        c = capacity
        #in : 1 x 5000 x 1
        self.conv1 = nn.Conv1d(in_channels=1, out_channels=c, kernel_size=20, stride=2, padding=1) # out: c x 2492 x 1 
        self.conv2 = nn.Conv1d(in_channels=c, out_channels=c*2, kernel_size=10, stride=2, padding=1) # out: c*2 x 1243 x 1 
        self.conv3 = nn.Conv1d(in_channels=c*2, out_channels=c*2, kernel_size=5, stride=2, padding=1) # out: c*2 x 621 x 1 
        self.fc_mu = nn.Linear(in_features=c*2*621, out_features=latent_dims)
        self.fc_logvar = nn.Linear(in_features=c*2*621, out_features=latent_dims)
            
    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = torch.flatten(x) # flatten batch of multi-channel feature maps to a batch of feature vectors
        x_mu = self.fc_mu(x)
        x_logvar = self.fc_logvar(x)
        return x_mu, x_logvar

class Decoder(nn.Module):
    def __init__(self):
        super(Decoder, self).__init__()
        c = capacity
        self.fc = nn.Linear(in_features=latent_dims, out_features=c*2*621)
        self.conv3 = nn.ConvTranspose1d(in_channels=c*2, out_channels=c*2, kernel_size=5, stride=2, padding=1)
        self.conv2 = nn.ConvTranspose1d(in_channels=c*2, out_channels=c, kernel_size=10, stride=2, padding=1)
        self.conv1 = nn.ConvTranspose1d(in_channels=c, out_channels=1, kernel_size=20, stride=2, padding=1)
            
    def forward(self, x):
        x = self.fc(x)
        x = torch.reshape(x,(capacity*2,621)) # unflatten batch of feature vectors to a batch of multi-channel feature maps
        x = F.relu(self.conv3(x))
        x = F.relu(self.conv2(x))
        x = torch.sigmoid(self.conv1(x)) # last layer before output is sigmoid, since we are using BCE as reconstruction loss
        return x
    
class VariationalAutoencoder(nn.Module):
    def __init__(self):
        super(VariationalAutoencoder, self).__init__()
        self.encoder = Encoder()
        self.decoder = Decoder()
    
    def forward(self, x):
        latent_mu, latent_logvar = self.encoder(x)
        latent = self.latent_sample(latent_mu, latent_logvar)
        x_recon = self.decoder(latent)
        return x_recon, latent_mu, latent_logvar
    
    def latent_sample(self, mu, logvar):
        if self.training:
            # the reparameterization trick
            std = logvar.mul(0.5).exp_()
            eps = torch.empty_like(std).normal_()
            return eps.mul(std).add_(mu)
        else:
            return mu
    
def ELBO_loss(recon_x, x, mu, logvar):
    # recon_x is the probability of a multivariate Bernoulli distribution p.
    # -log(p(x)) is then the pixel-wise cross-entropy.
    # Averaging or not averaging the cross-entropy over all pixels here
    # is a subtle detail with big effect on training, since it changes the weight
    # we need to pick for the other loss term by several orders of magnitude.
    # Not averaging is the direct implementation of the negative log likelihood,
    # but averaging makes the weight of the other loss term independent of the sequence resolution.
    recon_loss = F.cross_entropy(recon_x, x, reduction='sum')
    
    # KL-divergence between the prior distribution over latent vectors
    # and the distribution estimated by the generator for the given sequence.
    kldivergence = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())

    return recon_loss, variational_beta * kldivergence, recon_loss + (variational_beta * kldivergence)
    
vae32 = VariationalAutoencoder()

device = torch.device("cuda:0" if use_gpu and torch.cuda.is_available() else "cpu")
vae32 = vae32.to(device)

optimizer = torch.optim.Adam(params=vae32.parameters(), lr=learning_rate)
for epoch in range(num_epochs):
  vae32.train()
  num_batches = 0

  #Subset of samples to train
  permutated_train_tensor =  torch.tensor(np.random.permutation(train_tensor)[:20000])

  for tensor_batch in permutated_train_tensor:

    tensor_batch = tensor_batch.to(device)

    tensor_batch_recon, latent_mu, latent_logvar = vae32(tensor_batch)
    # reconstruction error
    recon_loss,reg_loss, loss = ELBO_loss(tensor_batch_recon, tensor_batch, latent_mu, latent_logvar)
    # backpropagation
    optimizer.zero_grad()
    loss.backward()
    
    # one step of the optmizer (using the gradients from backpropagation)
    optimizer.step()
    num_batches += 1
  
torch.save(vae32, 'vae32.pth')

use_gpu = True
latent_dims = 64
num_epochs = 10
capacity = 32
learning_rate = 2e-5
variational_beta = 10

class Encoder(nn.Module):
    def __init__(self):
        super(Encoder, self).__init__()
        c = capacity
        #in : 1 x 5000 x 1
        self.conv1 = nn.Conv1d(in_channels=1, out_channels=c, kernel_size=20, stride=2, padding=1) # out: c x 2492 x 1 
        self.conv2 = nn.Conv1d(in_channels=c, out_channels=c*2, kernel_size=10, stride=2, padding=1) # out: c*2 x 1243 x 1 
        self.conv3 = nn.Conv1d(in_channels=c*2, out_channels=c*2, kernel_size=5, stride=2, padding=1) # out: c*2 x 621 x 1 
        self.fc_mu = nn.Linear(in_features=c*2*621, out_features=latent_dims)
        self.fc_logvar = nn.Linear(in_features=c*2*621, out_features=latent_dims)
            
    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = torch.flatten(x) # flatten batch of multi-channel feature maps to a batch of feature vectors
        x_mu = self.fc_mu(x)
        x_logvar = self.fc_logvar(x)
        return x_mu, x_logvar

class Decoder(nn.Module):
    def __init__(self):
        super(Decoder, self).__init__()
        c = capacity
        self.fc = nn.Linear(in_features=latent_dims, out_features=c*2*621)
        self.conv3 = nn.ConvTranspose1d(in_channels=c*2, out_channels=c*2, kernel_size=5, stride=2, padding=1)
        self.conv2 = nn.ConvTranspose1d(in_channels=c*2, out_channels=c, kernel_size=10, stride=2, padding=1)
        self.conv1 = nn.ConvTranspose1d(in_channels=c, out_channels=1, kernel_size=20, stride=2, padding=1)
            
    def forward(self, x):
        x = self.fc(x)
        x = torch.reshape(x,(capacity*2,621)) # unflatten batch of feature vectors to a batch of multi-channel feature maps
        x = F.relu(self.conv3(x))
        x = F.relu(self.conv2(x))
        x = torch.sigmoid(self.conv1(x)) # last layer before output is sigmoid, since we are using BCE as reconstruction loss
        return x
    
class VariationalAutoencoder(nn.Module):
    def __init__(self):
        super(VariationalAutoencoder, self).__init__()
        self.encoder = Encoder()
        self.decoder = Decoder()
    
    def forward(self, x):
        latent_mu, latent_logvar = self.encoder(x)
        latent = self.latent_sample(latent_mu, latent_logvar)
        x_recon = self.decoder(latent)
        return x_recon, latent_mu, latent_logvar
    
    def latent_sample(self, mu, logvar):
        if self.training:
            # the reparameterization trick
            std = logvar.mul(0.5).exp_()
            eps = torch.empty_like(std).normal_()
            return eps.mul(std).add_(mu)
        else:
            return mu
    
def ELBO_loss(recon_x, x, mu, logvar):
    # recon_x is the probability of a multivariate Bernoulli distribution p.
    # -log(p(x)) is then the pixel-wise cross-entropy.
    # Averaging or not averaging the cross-entropy over all pixels here
    # is a subtle detail with big effect on training, since it changes the weight
    # we need to pick for the other loss term by several orders of magnitude.
    # Not averaging is the direct implementation of the negative log likelihood,
    # but averaging makes the weight of the other loss term independent of the sequence resolution.
    recon_loss = F.cross_entropy(recon_x, x, reduction='sum')
    
    # KL-divergence between the prior distribution over latent vectors
    # and the distribution estimated by the generator for the given sequence.
    kldivergence = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())

    return recon_loss, variational_beta * kldivergence, recon_loss + (variational_beta * kldivergence)
    
vae64 = VariationalAutoencoder()

device = torch.device("cuda:0" if use_gpu and torch.cuda.is_available() else "cpu")
vae64 = vae64.to(device)

optimizer = torch.optim.Adam(params=vae64.parameters(), lr=learning_rate)
for epoch in range(num_epochs):
  vae64.train()
  num_batches = 0

  #Subset of samples to train
  permutated_train_tensor =  torch.tensor(np.random.permutation(train_tensor)[:20000])

  for tensor_batch in permutated_train_tensor:

    tensor_batch = tensor_batch.to(device)

    tensor_batch_recon, latent_mu, latent_logvar = vae64(tensor_batch)
    # reconstruction error
    recon_loss,reg_loss, loss = ELBO_loss(tensor_batch_recon, tensor_batch, latent_mu, latent_logvar)
    # backpropagation
    optimizer.zero_grad()
    loss.backward()
    
    # one step of the optmizer (using the gradients from backpropagation)
    optimizer.step()
    num_batches += 1
  
  
torch.save(vae64, 'vae64.pth')

use_gpu = True
latent_dims = 64
num_epochs = 10
capacity = 32
learning_rate = 2e-5
variational_beta = 10

class Encoder(nn.Module):
    def __init__(self):
        super(Encoder, self).__init__()
        c = capacity
        #in : 1 x 5000 x 1
        self.conv1 = nn.Conv1d(in_channels=1, out_channels=c, kernel_size=20, stride=2, padding=1) # out: c x 2492 x 1 
        self.conv2 = nn.Conv1d(in_channels=c, out_channels=c*2, kernel_size=10, stride=2, padding=1) # out: c*2 x 1243 x 1 
        self.conv3 = nn.Conv1d(in_channels=c*2, out_channels=c*2, kernel_size=5, stride=2, padding=1) # out: c*2 x 621 x 1 
        self.fc_lambda = nn.Linear(in_features=c*2*621, out_features=latent_dims)
            
    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = torch.flatten(x) # flatten batch of multi-channel feature maps to a batch of feature vectors
        x_lambda = self.fc_lambda(x)
        return x_lambda

class Decoder(nn.Module):
    def __init__(self):
        super(Decoder, self).__init__()
        c = capacity
        self.fc = nn.Linear(in_features=latent_dims, out_features=c*2*621)
        self.conv3 = nn.ConvTranspose1d(in_channels=c*2, out_channels=c*2, kernel_size=5, stride=2, padding=1)
        self.conv2 = nn.ConvTranspose1d(in_channels=c*2, out_channels=c, kernel_size=10, stride=2, padding=1)
        self.conv1 = nn.ConvTranspose1d(in_channels=c, out_channels=1, kernel_size=20, stride=2, padding=1)
            
    def forward(self, x):
        x = self.fc(x)
        x = torch.reshape(x,(capacity*2,621)) # unflatten batch of feature vectors to a batch of multi-channel feature maps
        x = F.relu(self.conv3(x))
        x = F.relu(self.conv2(x))
        x = torch.sigmoid(self.conv1(x)) # last layer before output is sigmoid, since we are using BCE as reconstruction loss
        return x
    
class VariationalAutoencoder(nn.Module):
    def __init__(self):
        super(VariationalAutoencoder, self).__init__()
        self.encoder = Encoder()
        self.decoder = Decoder()
    
    def forward(self, x):
        latent_lambda = self.encoder(x)
        latent = self.latent_sample(latent_lambda)
        x_recon = self.decoder(latent)
        return x_recon, latent_lambda
    
    def latent_sample(self, latent_lambda):
        #exponential sampling 
        return torch.empty_like(latent_lambda).exponential_()
    
def ELBO_loss(recon_x, x, latent_lambda):
    # recon_x is the probability of a multivariate Bernoulli distribution p.
    # -log(p(x)) is then the pixel-wise cross-entropy.
    # Averaging or not averaging the cross-entropy over all pixels here
    # is a subtle detail with big effect on training, since it changes the weight
    # we need to pick for the other loss term by several orders of magnitude.
    # Not averaging is the direct implementation of the negative log likelihood,
    # but averaging makes the weight of the other loss term independent of the sequence resolution.
    recon_loss = F.cross_entropy(recon_x, x, reduction='sum')
    
    # KL-divergence between the prior distribution over latent vectors
    # and the distribution estimated by the generator for the given sequence.

    #KL divergence with prior as exponential distribution of lambda = 1
    kldivergence = torch.sum(latent_lambda.log( ) + 1/(latent_lambda) - 1)
    return recon_loss, variational_beta * kldivergence, recon_loss + (variational_beta * kldivergence)
    
vae64_e = VariationalAutoencoder()

device = torch.device("cuda:0" if use_gpu and torch.cuda.is_available() else "cpu")
vae64_e = vae64_e.to(device)   

optimizer = torch.optim.Adam(params=vae64_e.parameters(), lr=learning_rate)

for epoch in range(num_epochs):
  vae64_e.train()
  num_batches = 0

  #Subset of samples to train
  permutated_train_tensor =  torch.tensor(np.random.permutation(train_tensor)[:20000])#

  for tensor_batch in permutated_train_tensor:

    tensor_batch = tensor_batch.to(device)

    tensor_batch_recon, latent_lambda = vae64_e(tensor_batch)
    # reconstruction error
    recon_loss,reg_loss, loss = ELBO_loss(tensor_batch_recon, tensor_batch, latent_lambda)                       
    # backpropagation
    optimizer.zero_grad()
    loss.backward()
    
    # one step of the optmizer (using the gradients from backpropagation)
    optimizer.step()
    num_batches += 1

torch.save(vae64_e, 'vae64_e.pth')